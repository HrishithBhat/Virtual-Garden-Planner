from database.connection import get_db_cursor, close_db
from werkzeug.security import generate_password_hash, check_password_hash

class Expert:
    def __init__(self, id=None, name=None, email=None, password_hash=None, expertise=None, bio=None, profile_photo_url=None, resume_path=None, samples_path=None, status='pending', user_id=None, approved_at=None, created_at=None):
        self.id = id
        self.name = name
        self.email = email
        self.password_hash = password_hash
        self.expertise = expertise
        self.bio = bio
        self.profile_photo_url = profile_photo_url
        self.resume_path = resume_path
        self.samples_path = samples_path
        self.status = status or 'pending'
        self.user_id = user_id
        self.approved_at = approved_at
        self.created_at = created_at

    @classmethod
    def register(cls, name, email, password, expertise, bio=None, profile_photo_url=None, resume_path=None, samples_path=None):
        conn, cur = get_db_cursor()
        try:
            pw_hash = generate_password_hash(password)
            cur.execute(
                '''INSERT INTO experts (name, email, password_hash, expertise, bio, profile_photo_url, resume_path, samples_path, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending')
                   RETURNING id, created_at''',
                (name, email, pw_hash, expertise, bio, profile_photo_url, resume_path, samples_path)
            )
            row = cur.fetchone()
            conn.commit()
            return cls(id=row['id'], name=name, email=email, password_hash=pw_hash, expertise=expertise, bio=bio, profile_photo_url=profile_photo_url, resume_path=resume_path, samples_path=samples_path, status='pending', created_at=row['created_at'])
        except Exception as e:
            conn.rollback()
            print(f"Error registering expert: {e}")
            raise e
        finally:
            close_db(conn, cur)

    @classmethod
    def get_by_email(cls, email):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT * FROM experts WHERE email = %s LIMIT 1', (email,))
            r = cur.fetchone()
            return cls(**r) if r else None
        except Exception as e:
            print(f"Error get_by_email expert: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def get_by_id(cls, expert_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT * FROM experts WHERE id = %s', (expert_id,))
            r = cur.fetchone()
            return cls(**r) if r else None
        except Exception as e:
            print(f"Error get_by_id expert: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def get_by_user_id(cls, user_id):
        if not user_id:
            return None
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT * FROM experts WHERE user_id = %s LIMIT 1', (user_id,))
            row = cur.fetchone()
            return cls(**row) if row else None
        except Exception as e:
            print(f"Error get_by_user_id expert: {e}")
            return None
        finally:
            close_db(conn, cur)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @classmethod
    def get_pending(cls):
        conn, cur = get_db_cursor()
        try:
            cur.execute("SELECT * FROM experts WHERE status = 'pending' ORDER BY id ASC")
            rows = cur.fetchall() or []
            return [cls(**r) for r in rows]
        except Exception as e:
            print(f"Error fetching pending experts: {e}")
            return []
        finally:
            close_db(conn, cur)

    @classmethod
    def get_approved(cls, expertise=None, q=None):
        conn, cur = get_db_cursor()
        try:
            base = "SELECT * FROM experts WHERE status = 'approved'"
            params = []
            if expertise:
                base += " AND LOWER(expertise) = LOWER(%s)"; params.append(expertise)
            if q:
                base += " AND (LOWER(name) LIKE %s OR LOWER(expertise) LIKE %s OR LOWER(COALESCE(bio,'')) LIKE %s)"
                like = f"%{(q or '').lower()}%"
                params.extend([like, like, like])
            base += " ORDER BY name ASC"
            cur.execute(base, tuple(params))
            rows = cur.fetchall() or []
            return [cls(**r) for r in rows]
        except Exception as e:
            print(f"Error fetching approved experts: {e}")
            return []
        finally:
            close_db(conn, cur)

    @classmethod
    def get_all(cls):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT * FROM experts ORDER BY id ASC')
            rows = cur.fetchall() or []
            return [cls(**r) for r in rows]
        except Exception as e:
            print(f"Error fetching experts: {e}")
            return []
        finally:
            close_db(conn, cur)

    @classmethod
    def approve(cls, expert_id):
        conn, cur = get_db_cursor()
        try:
            # Fetch expert
            cur.execute('SELECT * FROM experts WHERE id = %s FOR UPDATE', (expert_id,))
            e = cur.fetchone()
            if not e:
                return False
            if (e.get('status') or '') == 'approved':
                return True
            # Ensure a users entry exists with role 'expert'
            # Create a unique username from name/email
            username_base = (e.get('name') or e.get('email') or 'expert').split('@')[0]
            import re
            uname = re.sub(r'[^a-zA-Z0-9_]+', '', username_base) or 'expert'
            uname = uname.lower()[:30]
            candidate = uname
            tries = 0
            while True:
                cur.execute('SELECT id FROM users WHERE username = %s', (candidate,))
                if not cur.fetchone():
                    break
                tries += 1
                candidate = f"{uname}{tries}"
            # Set a random password for created user (expert will use expert login flow)
            pw_hash = e.get('password_hash') or generate_password_hash('changeme')
            # If email exists in users, reuse it
            cur.execute('SELECT id FROM users WHERE email = %s', (e.get('email'),))
            user_row = cur.fetchone()
            if user_row:
                user_id = user_row['id']
                # ensure role is expert
                try:
                    cur.execute("UPDATE users SET role = 'expert' WHERE id = %s", (user_id,))
                except Exception:
                    pass
            else:
                cur.execute(
                    "INSERT INTO users (username, email, password_hash, role) VALUES (%s, %s, %s, 'expert') RETURNING id",
                    (candidate, e.get('email'), pw_hash)
                )
                user_row = cur.fetchone(); user_id = user_row['id']
            # Update expert status
            cur.execute(
                "UPDATE experts SET status='approved', approved_at=CURRENT_TIMESTAMP, user_id=%s WHERE id = %s",
                (user_id, expert_id)
            )
            conn.commit()
            return True
        except Exception as ex:
            conn.rollback()
            print(f"Error approving expert: {ex}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def reject(cls, expert_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute("UPDATE experts SET status='rejected' WHERE id = %s", (expert_id,))
            conn.commit()
            return True
        except Exception as ex:
            conn.rollback()
            print(f"Error rejecting expert: {ex}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def delete_by_id(cls, expert_id):
        conn, cur = get_db_cursor()
        try:
            # Fetch to get linked user
            cur.execute('SELECT user_id FROM experts WHERE id = %s', (expert_id,))
            row = cur.fetchone()
            if not row:
                return False
            user_id = row.get('user_id')
            # Delete expert first
            cur.execute('DELETE FROM experts WHERE id = %s', (expert_id,))
            deleted = cur.rowcount
            if deleted and user_id:
                try:
                    cur.execute('DELETE FROM users WHERE id = %s', (user_id,))
                except Exception as e:
                    print(f"Warning: failed to delete linked user {user_id}: {e}")
            conn.commit()
            return deleted > 0
        except Exception as e:
            conn.rollback()
            print(f"Error deleting expert: {e}")
            return False
        finally:
            close_db(conn, cur)

class User:
    def __init__(self, id=None, username=None, email=None, password_hash=None, role='user', is_pro=False, created_at=None, updated_at=None):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role or 'user'
        self.is_pro = bool(is_pro)
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def create(cls, username, email, password, role='user', is_pro=False):
        """Create a new user with optional role and pro flag"""
        conn, cur = get_db_cursor()
        try:
            password_hash = generate_password_hash(password)
            # Insert with explicit is_pro column (defaults to FALSE if not provided in older DBs)
            cur.execute(
                'INSERT INTO users (username, email, password_hash, role, is_pro) VALUES (%s, %s, %s, %s, %s) RETURNING id, created_at, updated_at',
                (username, email, password_hash, role, bool(is_pro))
            )
            result = cur.fetchone()
            conn.commit()
            return cls(
                id=result['id'],
                username=username,
                email=email,
                password_hash=password_hash,
                role=role,
                is_pro=bool(is_pro),
                created_at=result['created_at'],
                updated_at=result['updated_at']
            )
        except Exception as e:
            conn.rollback()
            print(f"Error creating user: {e}")
            raise e
        finally:
            close_db(conn, cur)
    
    @classmethod
    def get_by_username(cls, username):
        """Get user by username"""
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT * FROM users WHERE username = %s', (username,))
            user_data = cur.fetchone()
            if user_data:
                return cls(**user_data)
            return None
        except Exception as e:
            print(f"Error getting user by username: {e}")
            return None
        finally:
            close_db(conn, cur)
    
    @classmethod
    def get_by_email(cls, email):
        """Get user by email"""
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT * FROM users WHERE email = %s', (email,))
            user_data = cur.fetchone()
            if user_data:
                return cls(**user_data)
            return None
        except Exception as e:
            print(f"Error getting user by email: {e}")
            return None
        finally:
            close_db(conn, cur)
    
    def check_password(self, password):
        """Check if password matches"""
        return check_password_hash(self.password_hash, password)
    
    @classmethod
    def user_exists(cls, username, email):
        """Check if user with username or email exists"""
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT id FROM users WHERE username = %s OR email = %s', (username, email))
            return cur.fetchone() is not None
        except Exception as e:
            print(f"Error checking user existence: {e}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def get_all(cls):
        """Return all users (excluding password hash)"""
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT id, username, email, role, is_pro, created_at, updated_at FROM users ORDER BY id ASC')
            rows = cur.fetchall()
            return [cls(**r) for r in rows]
        except Exception as e:
            print(f"Error fetching users: {e}")
            return []
        finally:
            close_db(conn, cur)

    @classmethod
    def delete_by_id(cls, user_id):
        """Delete a user by id"""
        conn, cur = get_db_cursor()
        try:
            cur.execute('DELETE FROM users WHERE id = %s', (user_id,))
            deleted = cur.rowcount
            conn.commit()
            return deleted > 0
        except Exception as e:
            conn.rollback()
            print(f"Error deleting user: {e}")
            return False
        finally:
            close_db(conn, cur)

    # Garden related methods
    @classmethod
    def add_to_garden(cls, user_id, plant_id, nickname=None, planted_on=None, quantity=1, location=None, watering_interval_days=None, notes=None, last_watered=None):
        conn, cur = get_db_cursor()
        try:
            # Try to update existing entry first
            cur.execute('''
                UPDATE user_gardens
                SET nickname=%s, planted_on=%s, quantity=%s, location=%s, watering_interval_days=%s, notes=%s, last_watered=%s, created_at = COALESCE(created_at, CURRENT_TIMESTAMP)
                WHERE user_id = %s AND plant_id = %s
                RETURNING id
            ''', (nickname, planted_on, quantity, location, watering_interval_days, notes, last_watered, user_id, plant_id))
            res = cur.fetchone()
            if res:
                conn.commit()
                return True

            # If no existing row, insert new
            cur.execute('''
                INSERT INTO user_gardens (user_id, plant_id, nickname, planted_on, quantity, location, watering_interval_days, notes, last_watered)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (user_id, plant_id, nickname, planted_on, quantity, location, watering_interval_days, notes, last_watered))
            res2 = cur.fetchone()
            conn.commit()
            return res2 is not None
        except Exception as e:
            conn.rollback()
            print(f"Error adding to garden: {e}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def remove_from_garden(cls, user_id, plant_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('DELETE FROM user_gardens WHERE user_id = %s AND plant_id = %s', (user_id, plant_id))
            deleted = cur.rowcount
            conn.commit()
            return deleted > 0
        except Exception as e:
            conn.rollback()
            print(f"Error removing from garden: {e}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def get_garden(cls, user_id):
        """Return list of garden items (with plant info) for a user"""
        conn, cur = get_db_cursor()
        try:
            cur.execute('''
                SELECT ug.id as garden_id, ug.user_id, ug.plant_id, ug.nickname, ug.planted_on, ug.quantity, ug.location, ug.watering_interval_days, ug.notes, ug.last_watered,
                       (SELECT s.id FROM schedules s WHERE s.garden_id = ug.id ORDER BY s.id DESC LIMIT 1) as schedule_id,
                       p.id as plant_id, p.name, p.scientific_name, p.duration_days, p.type, p.photo_url, p.description, p.created_by
                FROM user_gardens ug
                JOIN plants p ON p.id = ug.plant_id
                WHERE ug.user_id = %s
                ORDER BY ug.id ASC
            ''', (user_id,))
            rows = cur.fetchall()
            items = []
            for r in rows:
                item = {
                    'garden_id': r['garden_id'],
                    'user_id': r['user_id'],
                    'plant_id': r['plant_id'],
                    'nickname': r.get('nickname'),
                    'planted_on': r.get('planted_on'),
                    'quantity': r.get('quantity'),
                    'location': r.get('location'),
                    'watering_interval_days': r.get('watering_interval_days'),
                    'notes': r.get('notes'),
                    'last_watered': r.get('last_watered'),
                    'schedule_id': r.get('schedule_id'),
                    'is_creator': True if (r.get('created_by') == user_id) else False,
                    'plant': {
                        'id': r['plant_id'],
                        'name': r['name'],
                        'scientific_name': r['scientific_name'],
                        'duration_days': r.get('duration_days'),
                        'type': r.get('type'),
                        'photo_url': r.get('photo_url'),
                        'description': r.get('description')
                    }
                }
                items.append(item)
            return items
        except Exception as e:
            print(f"Error fetching user garden: {e}")
            return []
        finally:
            close_db(conn, cur)

    @classmethod
    def update_garden_item(cls, garden_id, user_id, nickname=None, planted_on=None, quantity=None, location=None, watering_interval_days=None, notes=None, last_watered=None):
        conn, cur = get_db_cursor()
        try:
            # Build dynamic set clause
            fields = []
            values = []
            if nickname is not None:
                fields.append('nickname = %s'); values.append(nickname)
            if planted_on is not None:
                fields.append('planted_on = %s'); values.append(planted_on)
            if quantity is not None:
                fields.append('quantity = %s'); values.append(quantity)
            if location is not None:
                fields.append('location = %s'); values.append(location)
            if watering_interval_days is not None:
                fields.append('watering_interval_days = %s'); values.append(watering_interval_days)
            if notes is not None:
                fields.append('notes = %s'); values.append(notes)
            if last_watered is not None:
                fields.append('last_watered = %s'); values.append(last_watered)
            if not fields:
                return False
            set_clause = ', '.join(fields) + ', updated_at = CURRENT_TIMESTAMP'
            values.extend([garden_id, user_id])
            query = f'UPDATE user_gardens SET {set_clause} WHERE id = %s AND user_id = %s RETURNING id'
            cur.execute(query, tuple(values))
            res = cur.fetchone()
            conn.commit()
            return res is not None
        except Exception as e:
            conn.rollback()
            print(f"Error updating garden item: {e}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def get_last_garden_item(cls, user_id):
        """Return the most recently added Plant in user's garden or None"""
        conn, cur = get_db_cursor()
        try:
            cur.execute('''
                SELECT p.id, p.name, p.scientific_name, p.duration_days, p.type, p.photo_url, p.description, p.created_at, p.updated_at
                FROM plants p
                JOIN user_gardens ug ON ug.plant_id = p.id
                WHERE ug.user_id = %s
                ORDER BY ug.id DESC
                LIMIT 1
            ''', (user_id,))
            row = cur.fetchone()
            if row:
                return Plant(**row)
            return None
        except Exception as e:
            print(f"Error fetching last garden item: {e}")
            return None
        finally:
            close_db(conn, cur)


class GardenJournal:
    def __init__(
        self,
        id=None,
        user_id=None,
        plant_id=None,
        garden_id=None,
        title=None,
        created_at=None,
        updated_at=None,
        plant_name=None,
        plant_scientific_name=None,
        plant_photo=None,
        entry_count=0,
        latest_entry_date=None
    ):
        self.id = id
        self.user_id = user_id
        self.plant_id = plant_id
        self.garden_id = garden_id
        self.title = title
        self.created_at = created_at
        self.updated_at = updated_at
        self.plant_name = plant_name
        self.plant_scientific_name = plant_scientific_name
        self.plant_photo = plant_photo
        self.entry_count = entry_count
        self.latest_entry_date = latest_entry_date

    @classmethod
    def create(cls, user_id, plant_id, title, garden_id=None):
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                '''
                INSERT INTO garden_journals (user_id, plant_id, garden_id, title)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, plant_id, title)
                DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                RETURNING id, user_id, plant_id, garden_id, title, created_at, updated_at
                ''',
                (user_id, plant_id, garden_id, title)
            )
            row = cur.fetchone()
            conn.commit()
            if row:
                return cls(**row)
            return None
        except Exception as e:
            conn.rollback()
            print(f"Error creating garden journal: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def get_or_create(cls, user_id, plant_id, title=None, garden_id=None):
        if not title:
            plant = Plant.get_by_id(plant_id)
            title = plant.name if plant and getattr(plant, 'name', None) else 'Garden Journal'
        existing = cls.find_by_title(user_id, plant_id, title)
        if existing:
            return existing
        return cls.create(user_id, plant_id, title, garden_id)

    @classmethod
    def find_by_title(cls, user_id, plant_id, title):
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                '''
                SELECT * FROM garden_journals
                WHERE user_id = %s AND plant_id = %s AND title = %s
                LIMIT 1
                ''',
                (user_id, plant_id, title)
            )
            row = cur.fetchone()
            return cls(**row) if row else None
        except Exception as e:
            print(f"Error finding garden journal by title: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def list_for_user(cls, user_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                '''
                SELECT
                    gj.*,
                    p.name AS plant_name,
                    p.scientific_name AS plant_scientific_name,
                    p.photo_url AS plant_photo,
                    COUNT(e.id) AS entry_count,
                    MAX(e.entry_date) AS latest_entry_date
                FROM garden_journals gj
                LEFT JOIN plants p ON p.id = gj.plant_id
                LEFT JOIN garden_journal_entries e ON e.journal_id = gj.id
                WHERE gj.user_id = %s
                GROUP BY gj.id, p.name, p.scientific_name, p.photo_url
                ORDER BY COALESCE(MAX(e.entry_date), gj.updated_at, gj.created_at) DESC
                ''',
                (user_id,)
            )
            rows = cur.fetchall() or []
            journals = []
            for row in rows:
                journals.append(
                    cls(
                        id=row['id'],
                        user_id=row['user_id'],
                        plant_id=row['plant_id'],
                        garden_id=row.get('garden_id'),
                        title=row['title'],
                        created_at=row.get('created_at'),
                        updated_at=row.get('updated_at'),
                        plant_name=row.get('plant_name'),
                        plant_scientific_name=row.get('plant_scientific_name'),
                        plant_photo=row.get('plant_photo'),
                        entry_count=row.get('entry_count') or 0,
                        latest_entry_date=row.get('latest_entry_date')
                    )
                )
            return journals
        except Exception as e:
            print(f"Error listing garden journals: {e}")
            return []
        finally:
            close_db(conn, cur)

    @classmethod
    def get_for_user(cls, journal_id, user_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                '''
                SELECT
                    gj.*,
                    p.name AS plant_name,
                    p.scientific_name AS plant_scientific_name,
                    p.photo_url AS plant_photo
                FROM garden_journals gj
                LEFT JOIN plants p ON p.id = gj.plant_id
                WHERE gj.id = %s AND gj.user_id = %s
                LIMIT 1
                ''',
                (journal_id, user_id)
            )
            row = cur.fetchone()
            if row:
                return cls(
                    id=row['id'],
                    user_id=row['user_id'],
                    plant_id=row['plant_id'],
                    garden_id=row.get('garden_id'),
                    title=row['title'],
                    created_at=row.get('created_at'),
                    updated_at=row.get('updated_at'),
                    plant_name=row.get('plant_name'),
                    plant_scientific_name=row.get('plant_scientific_name'),
                    plant_photo=row.get('plant_photo')
                )
            return None
        except Exception as e:
            print(f"Error fetching garden journal: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def update_metadata(cls, journal_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('UPDATE garden_journals SET updated_at = CURRENT_TIMESTAMP WHERE id = %s', (journal_id,))
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error updating garden journal metadata: {e}")
        finally:
            close_db(conn, cur)


class GardenJournalEntry:
    def __init__(
        self,
        id=None,
        journal_id=None,
        entry_date=None,
        growth_height_cm=None,
        growth_width_cm=None,
        notes=None,
        photo_path=None,
        created_at=None,
        updated_at=None
    ):
        self.id = id
        self.journal_id = journal_id
        self.entry_date = entry_date
        self.growth_height_cm = growth_height_cm
        self.growth_width_cm = growth_width_cm
        self.notes = notes
        self.photo_path = photo_path
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def list_for_journal(cls, journal_id, user_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                '''
                SELECT e.*
                FROM garden_journal_entries e
                JOIN garden_journals j ON j.id = e.journal_id
                WHERE e.journal_id = %s AND j.user_id = %s
                ORDER BY e.entry_date ASC, e.created_at ASC
                ''',
                (journal_id, user_id)
            )
            rows = cur.fetchall() or []
            return [cls(**row) for row in rows]
        except Exception as e:
            print(f"Error listing garden journal entries: {e}")
            return []
        finally:
            close_db(conn, cur)

    @classmethod
    def get_for_user(cls, entry_id, user_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                '''
                SELECT e.*
                FROM garden_journal_entries e
                JOIN garden_journals j ON j.id = e.journal_id
                WHERE e.id = %s AND j.user_id = %s
                LIMIT 1
                ''',
                (entry_id, user_id)
            )
            row = cur.fetchone()
            return cls(**row) if row else None
        except Exception as e:
            print(f"Error fetching garden journal entry: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def create(cls, journal_id, user_id, entry_date, notes=None, growth_height_cm=None, growth_width_cm=None, photo_path=None):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT 1 FROM garden_journals WHERE id = %s AND user_id = %s', (journal_id, user_id))
            if not cur.fetchone():
                return None
            cur.execute(
                '''
                INSERT INTO garden_journal_entries (journal_id, entry_date, growth_height_cm, growth_width_cm, notes, photo_path)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, journal_id, entry_date, growth_height_cm, growth_width_cm, notes, photo_path, created_at, updated_at
                ''',
                (journal_id, entry_date, growth_height_cm, growth_width_cm, notes, photo_path)
            )
            row = cur.fetchone()
            conn.commit()
            if row:
                GardenJournal.update_metadata(journal_id)
                return cls(**row)
            return None
        except Exception as e:
            conn.rollback()
            print(f"Error creating garden journal entry: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def update(cls, entry_id, user_id, entry_date=None, notes=None, growth_height_cm=None, growth_width_cm=None, photo_path=None):
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                '''
                SELECT e.journal_id
                FROM garden_journal_entries e
                JOIN garden_journals j ON j.id = e.journal_id
                WHERE e.id = %s AND j.user_id = %s
                LIMIT 1
                ''',
                (entry_id, user_id)
            )
            row = cur.fetchone()
            if not row:
                return False
            journal_id = row['journal_id']
            clauses = []
            params = []
            if entry_date is not None:
                clauses.append('entry_date = %s')
                params.append(entry_date)
            if growth_height_cm is not None:
                clauses.append('growth_height_cm = %s')
                params.append(growth_height_cm)
            if growth_width_cm is not None:
                clauses.append('growth_width_cm = %s')
                params.append(growth_width_cm)
            if notes is not None:
                clauses.append('notes = %s')
                params.append(notes)
            if photo_path is not None:
                clauses.append('photo_path = %s')
                params.append(photo_path)
            clauses.append('updated_at = CURRENT_TIMESTAMP')
            query = f"UPDATE garden_journal_entries SET {', '.join(clauses)} WHERE id = %s RETURNING id"
            params.append(entry_id)
            cur.execute(query, tuple(params))
            updated = cur.fetchone()
            conn.commit()
            if updated:
                GardenJournal.update_metadata(journal_id)
            return bool(updated)
        except Exception as e:
            conn.rollback()
            print(f"Error updating garden journal entry: {e}")
            return False
        finally:
            close_db(conn, cur)


class Schedule:
    def __init__(self, id=None, garden_id=None, user_id=None, schedule_json=None, created_at=None):
        self.id = id
        self.garden_id = garden_id
        self.user_id = user_id
        self.schedule_json = schedule_json
        self.created_at = created_at

    @classmethod
    def create(cls, garden_id, user_id, schedule_json):
        conn, cur = get_db_cursor()
        try:
            cur.execute('INSERT INTO schedules (garden_id, user_id, schedule_json) VALUES (%s, %s, %s) RETURNING id, created_at', (garden_id, user_id, schedule_json))
            res = cur.fetchone()
            conn.commit()
            if res:
                return cls(id=res['id'], garden_id=garden_id, user_id=user_id, schedule_json=schedule_json, created_at=res['created_at'])
            return None
        except Exception as e:
            conn.rollback()
            print(f"Error creating schedule: {e}")
            raise e
        finally:
            close_db(conn, cur)

    @classmethod
    def get_by_id(cls, schedule_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT * FROM schedules WHERE id = %s', (schedule_id,))
            row = cur.fetchone()
            if row:
                return cls(**row)
            return None
        except Exception as e:
            print(f"Error getting schedule by id: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def get_by_garden(cls, garden_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT * FROM schedules WHERE garden_id = %s ORDER BY id DESC', (garden_id,))
            rows = cur.fetchall()
            return [cls(**r) for r in rows]
        except Exception as e:
            print(f"Error fetching schedules for garden: {e}")
            return []
        finally:
            close_db(conn, cur)


class Plant:
    def __init__(self, id=None, name=None, scientific_name=None, duration_days=None, type=None, photo_url=None, description=None, created_at=None, updated_at=None, created_by=None, sunlight=None, spacing_cm=None, watering_needs=None, model_url=None, growth_height_cm=None, growth_width_cm=None):
        self.id = id
        self.name = name
        self.scientific_name = scientific_name
        self.duration_days = duration_days
        self.type = type
        self.photo_url = photo_url
        self.description = description
        self.created_at = created_at
        self.updated_at = updated_at
        self.created_by = created_by
        self.sunlight = sunlight
        self.spacing_cm = spacing_cm
        self.watering_needs = watering_needs
        self.model_url = model_url
        self.growth_height_cm = growth_height_cm
        self.growth_width_cm = growth_width_cm

    @classmethod
    def create(cls, name, scientific_name, duration_days, plant_type, photo_url, description, created_by=None, sunlight=None, spacing_cm=None, watering_needs=None, model_url=None, growth_height_cm=None, growth_width_cm=None):
        conn, cur = get_db_cursor()
        try:
            cols = ['name','scientific_name','duration_days','type','photo_url','description']
            vals = [name, scientific_name, duration_days, plant_type, photo_url, description]
            if created_by is not None:
                cols.append('created_by'); vals.append(created_by)
            if sunlight is not None:
                cols.append('sunlight'); vals.append(sunlight)
            if spacing_cm is not None:
                cols.append('spacing_cm'); vals.append(spacing_cm)
            if watering_needs is not None:
                cols.append('watering_needs'); vals.append(watering_needs)
            if model_url is not None:
                cols.append('model_url'); vals.append(model_url)
            if growth_height_cm is not None:
                cols.append('growth_height_cm'); vals.append(growth_height_cm)
            if growth_width_cm is not None:
                cols.append('growth_width_cm'); vals.append(growth_width_cm)
            placeholders = ', '.join(['%s'] * len(vals))
            col_list = ', '.join(cols)
            sql = f"INSERT INTO plants ({col_list}) VALUES ({placeholders}) RETURNING id, created_at, updated_at"
            cur.execute(sql, tuple(vals))
            result = cur.fetchone()
            conn.commit()
            return cls(
                id=result['id'],
                name=name,
                scientific_name=scientific_name,
                duration_days=duration_days,
                type=plant_type,
                photo_url=photo_url,
                description=description,
                created_at=result['created_at'],
                updated_at=result['updated_at'],
                created_by=created_by,
                sunlight=sunlight,
                spacing_cm=spacing_cm,
                watering_needs=watering_needs,
                model_url=model_url,
                growth_height_cm=growth_height_cm,
                growth_width_cm=growth_width_cm
            )
        except Exception as e:
            conn.rollback()
            print(f"Error creating plant: {e}")
            raise e
        finally:
            close_db(conn, cur)

    @classmethod
    def get_all(cls):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT id, name, scientific_name, duration_days, type, photo_url, description, created_at, updated_at, created_by, sunlight, spacing_cm, watering_needs, model_url, growth_height_cm, growth_width_cm FROM plants ORDER BY id DESC')
            rows = cur.fetchall()
            return [cls(**r) for r in rows]
        except Exception as e:
            print(f"Error fetching plants: {e}")
            return []
        finally:
            close_db(conn, cur)

    @classmethod
    def get_by_id(cls, plant_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT id, name, scientific_name, duration_days, type, photo_url, description, created_at, updated_at, created_by, sunlight, spacing_cm, watering_needs, model_url, growth_height_cm, growth_width_cm FROM plants WHERE id = %s', (plant_id,))
            row = cur.fetchone()
            if row:
                return cls(**row)
            return None
        except Exception as e:
            print(f"Error getting plant by id: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def update(cls, plant_id, name, scientific_name, duration_days, plant_type, photo_url, description, sunlight=None, spacing_cm=None, watering_needs=None, model_url=None, growth_height_cm=None, growth_width_cm=None):
        conn, cur = get_db_cursor()
        try:
            fields = ['name=%s','scientific_name=%s','duration_days=%s','type=%s','photo_url=%s','description=%s']
            values = [name, scientific_name, duration_days, plant_type, photo_url, description]
            if sunlight is not None:
                fields.append('sunlight=%s'); values.append(sunlight)
            if spacing_cm is not None:
                fields.append('spacing_cm=%s'); values.append(spacing_cm)
            if watering_needs is not None:
                fields.append('watering_needs=%s'); values.append(watering_needs)
            if model_url is not None:
                fields.append('model_url=%s'); values.append(model_url)
            if growth_height_cm is not None:
                fields.append('growth_height_cm=%s'); values.append(growth_height_cm)
            if growth_width_cm is not None:
                fields.append('growth_width_cm=%s'); values.append(growth_width_cm)
            set_clause = ', '.join(fields) + ', updated_at = CURRENT_TIMESTAMP'
            values.append(plant_id)
            sql = f'UPDATE plants SET {set_clause} WHERE id = %s RETURNING id, updated_at'
            cur.execute(sql, tuple(values))
            result = cur.fetchone()
            conn.commit()
            return result is not None
        except Exception as e:
            conn.rollback()
            print(f"Error updating plant: {e}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def delete_by_id(cls, plant_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('DELETE FROM plants WHERE id = %s', (plant_id,))
            deleted = cur.rowcount
            conn.commit()
            return deleted > 0
        except Exception as e:
            conn.rollback()
            print(f"Error deleting plant: {e}")
            return False
        finally:
            close_db(conn, cur)


class ScheduleTask:
    @classmethod
    def create_many(cls, schedule_id, schedule_list):
        """Insert tasks for a schedule into schedule_tasks table"""
        conn, cur = get_db_cursor()
        try:
            # schedule_list expected as list of {day, tasks}
            for i, day_obj in enumerate(schedule_list, start=1):
                day_num = day_obj.get('day') if isinstance(day_obj, dict) and day_obj.get('day') else i
                tasks = day_obj.get('tasks') if isinstance(day_obj, dict) else []
                if not isinstance(tasks, list):
                    continue
                for idx, t in enumerate(tasks):
                    cur.execute('''
                        INSERT INTO schedule_tasks (schedule_id, day, task_index, task_text, completed) VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (schedule_id, day, task_index) DO UPDATE SET task_text = EXCLUDED.task_text
                    ''', (schedule_id, day_num, idx, t, False))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error creating schedule tasks: {e}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def toggle(cls, user_id, schedule_id, day, task_index, completed=False):
        conn, cur = get_db_cursor()
        try:
            # Ensure schedule belongs to user
            cur.execute('SELECT user_id, schedule_json FROM schedules WHERE id = %s', (schedule_id,))
            row = cur.fetchone()
            if not row or row.get('user_id') != user_id:
                return {'error': 'Not authorized'}, 403

            # Attempt to update existing task row
            if completed:
                cur.execute('''
                    UPDATE schedule_tasks
                    SET completed = TRUE, completed_at = CURRENT_TIMESTAMP
                    WHERE schedule_id = %s AND day = %s AND task_index = %s
                    RETURNING task_text
                ''', (schedule_id, day, task_index))
            else:
                cur.execute('''
                    UPDATE schedule_tasks
                    SET completed = FALSE, completed_at = NULL
                    WHERE schedule_id = %s AND day = %s AND task_index = %s
                    RETURNING task_text
                ''', (schedule_id, day, task_index))
            res = cur.fetchone()

            # If no existing row, derive the task text from schedule_json and insert
            task_text = None
            if not res:
                schedule_json = row.get('schedule_json')
                try:
                    import json as _json
                    parsed = _json.loads(schedule_json) if schedule_json else []
                    # find day object
                    target = None
                    for obj in parsed:
                        d = obj.get('day') if isinstance(obj, dict) else None
                        if d == day:
                            target = obj
                            break
                    if target is None and 1 <= day <= len(parsed):
                        target = parsed[day-1]
                    tasks_list = target.get('tasks') if isinstance(target, dict) else []
                    if isinstance(tasks_list, list) and 0 <= task_index < len(tasks_list):
                        task_text = tasks_list[task_index]
                    else:
                        task_text = f'Task {task_index+1}'
                except Exception:
                    task_text = f'Task {task_index+1}'

                # Insert the task row with completed state
                if completed:
                    cur.execute('''
                        INSERT INTO schedule_tasks (schedule_id, day, task_index, task_text, completed, completed_at)
                        VALUES (%s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP)
                        ON CONFLICT (schedule_id, day, task_index) DO UPDATE SET task_text = EXCLUDED.task_text, completed = EXCLUDED.completed, completed_at = EXCLUDED.completed_at
                        RETURNING task_text
                    ''', (schedule_id, day, task_index, task_text))
                else:
                    cur.execute('''
                        INSERT INTO schedule_tasks (schedule_id, day, task_index, task_text, completed)
                        VALUES (%s, %s, %s, %s, FALSE)
                        ON CONFLICT (schedule_id, day, task_index) DO UPDATE SET task_text = EXCLUDED.task_text, completed = EXCLUDED.completed
                        RETURNING task_text
                    ''', (schedule_id, day, task_index, task_text))
                res = cur.fetchone()

            conn.commit()
            if not res:
                return {'error': 'Task not found or could not be created'}, 404

            task_text = res.get('task_text')

            # Create notification about status change and include schedule link
            from backend.models import Notification
            msg = f"Task {'completed' if completed else 'unmarked'} for Day {day}: {task_text}"
            url = f"/garden/schedule/{schedule_id}#day-{day}"
            Notification.create(user_id, msg, schedule_id=schedule_id, day=day, url=url)
            try:
                if completed:
                    Notification.complete_pending(user_id, schedule_id, day, task_text)
                else:
                    Notification.ensure_pending(user_id, schedule_id, day, task_text, url=url)
            except Exception:
                pass
            return {'message': msg}
        except Exception as e:
            conn.rollback()
            print(f"Error toggling task: {e}")
            return {'error': str(e)}, 500
        finally:
            close_db(conn, cur)

    @classmethod
    def get_for_schedule(cls, schedule_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT id, schedule_id, day, task_index, task_text, completed, completed_at FROM schedule_tasks WHERE schedule_id = %s ORDER BY day ASC, task_index ASC', (schedule_id,))
            rows = cur.fetchall()
            return rows
        except Exception as e:
            print(f"Error fetching schedule tasks: {e}")
            return []
        finally:
            close_db(conn, cur)


class Notification:
    @classmethod
    def create(cls, user_id, message, schedule_id=None, day=None, url=None):
        conn, cur = get_db_cursor()
        try:
            cur.execute('INSERT INTO notifications (user_id, message, schedule_id, day, url) VALUES (%s, %s, %s, %s, %s)', (user_id, message, schedule_id, day, url))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error creating notification: {e}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def exists(cls, user_id, schedule_id, day, task_text):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT id FROM notifications WHERE user_id = %s AND schedule_id = %s AND day = %s AND message = %s LIMIT 1', (user_id, schedule_id, day, task_text))
            return cur.fetchone() is not None
        except Exception as e:
            print(f"Error checking notification exists: {e}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def get_for_user(cls, user_id, limit=50):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT id, message, url, is_read, created_at FROM notifications WHERE user_id = %s AND (is_read = FALSE OR is_read IS NULL) ORDER BY created_at DESC LIMIT %s', (user_id, limit))
            rows = cur.fetchall()
            return rows
        except Exception as e:
            print(f"Error fetching notifications: {e}")
            return []
        finally:
            close_db(conn, cur)

    @classmethod
    def clear_all_for_user(cls, user_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('UPDATE notifications SET is_read = TRUE WHERE user_id = %s', (user_id,))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error clearing notifications: {e}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def ensure_pending(cls, user_id, schedule_id, day, task_text, url=None):
        msg = f"Pending - Day {day}: {task_text}"
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT id FROM notifications WHERE user_id=%s AND schedule_id=%s AND day=%s AND message=%s AND (is_read = FALSE OR is_read IS NULL) LIMIT 1', (user_id, schedule_id, day, msg))
            row = cur.fetchone()
            if row:
                return True
            cur.execute('INSERT INTO notifications (user_id, message, schedule_id, day, url, is_read) VALUES (%s, %s, %s, %s, %s, FALSE)', (user_id, msg, schedule_id, day, url))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error ensuring pending notification: {e}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def complete_pending(cls, user_id, schedule_id, day, task_text):
        msg = f"Pending - Day {day}: {task_text}"
        conn, cur = get_db_cursor()
        try:
            cur.execute('UPDATE notifications SET is_read=TRUE WHERE user_id=%s AND schedule_id=%s AND day=%s AND message=%s AND (is_read = FALSE OR is_read IS NULL)', (user_id, schedule_id, day, msg))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error completing pending notification: {e}")
            return False
        finally:
            close_db(conn, cur)


class AIMemory:
    @staticmethod
    def _to_json(value):
        import json
        try:
            return json.dumps(value, ensure_ascii=False)
        except Exception:
            return None

    @staticmethod
    def _from_json(text):
        import json
        try:
            return json.loads(text) if text else None
        except Exception:
            return None

    @classmethod
    def upsert(cls, user_id, memory_type, key=None, value=None):
        conn, cur = get_db_cursor()
        try:
            v_json = cls._to_json(value)
            cur.execute(
                '''
                INSERT INTO ai_memories (user_id, memory_type, k, v_json)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, memory_type, k)
                DO UPDATE SET v_json = EXCLUDED.v_json, updated_at = CURRENT_TIMESTAMP
                RETURNING id
                ''',
                (user_id, memory_type, key, v_json)
            )
            row = cur.fetchone()
            conn.commit()
            return row and row.get('id')
        except Exception as e:
            conn.rollback()
            print(f"AIMemory upsert error: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def add_preference(cls, user_id, key, value):
        return cls.upsert(user_id, 'preference', key, value)

    @classmethod
    def add_care_event(cls, user_id, key, value):
        return cls.upsert(user_id, 'care_event', key, value)

    @classmethod
    def list_for_user(cls, user_id, memory_type=None):
        conn, cur = get_db_cursor()
        try:
            if memory_type:
                cur.execute('SELECT id, memory_type, k, v_json, created_at, updated_at FROM ai_memories WHERE user_id=%s AND memory_type=%s ORDER BY updated_at DESC, id DESC', (user_id, memory_type))
            else:
                cur.execute('SELECT id, memory_type, k, v_json, created_at, updated_at FROM ai_memories WHERE user_id=%s ORDER BY updated_at DESC, id DESC', (user_id,))
            rows = cur.fetchall() or []
            out = []
            for r in rows:
                out.append({
                    'id': r.get('id'),
                    'memory_type': r.get('memory_type'),
                    'key': r.get('k'),
                    'value': cls._from_json(r.get('v_json')),
                    'created_at': r.get('created_at'),
                    'updated_at': r.get('updated_at')
                })
            return out
        except Exception as e:
            print(f"AIMemory list error: {e}")
            return []
        finally:
            close_db(conn, cur)


class Rewards:
    ACTION_POINT_MAP = {
        'plant_care': 10,
        'journal_update': 8,
        'ai_detection': 6,
        'eco_action': 12,
        'community_post': 5,
        'ai_interaction': 2,
        'community_comment': 3,
        'community_answer': 10,
        'daily_login': 1
    }

    @classmethod
    def _is_pro(cls, user_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT is_pro FROM users WHERE id = %s', (user_id,))
            r = cur.fetchone() or {}
            return bool(r.get('is_pro'))
        except Exception:
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def award_points(cls, user_id, action_type, base_points=None, metadata=None):
        conn, cur = get_db_cursor()
        try:
            base = base_points if base_points is not None else cls.ACTION_POINT_MAP.get(action_type, 1)
            is_pro = cls._is_pro(user_id)
            multiplier = 1.1 if is_pro else 1.0
            points = int(round(base * multiplier))
            import json as _json
            meta_str = _json.dumps(metadata, ensure_ascii=False) if metadata is not None else None
            cur.execute('INSERT INTO rewards_points (user_id, action_type, points, multiplier, metadata) VALUES (%s,%s,%s,%s,%s) RETURNING id', (user_id, action_type, points, multiplier, meta_str))
            row = cur.fetchone()
            conn.commit()
            # Post-award checks
            try:
                # update streaks for plant care
                if action_type == 'plant_care':
                    cls._update_streak_on_care(user_id)
                # badge checks
                cls._maybe_award_badges(user_id)
            except Exception:
                pass
            return {'id': row.get('id') if row else None, 'points': points}
        except Exception as e:
            conn.rollback()
            print(f"Rewards award_points error: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def log_action(cls, user_id, action_type, metadata=None):
        base = cls.ACTION_POINT_MAP.get(action_type, 1)
        return cls.award_points(user_id, action_type, base_points=base, metadata=metadata)

    @classmethod
    def award_daily_login(cls, user_id):
        """Award 1 point for daily login once per calendar day (DB server date).
        Returns the award result or None if already awarded.
        """
        conn, cur = get_db_cursor()
        try:
            # Check if a daily_login record exists for today
            cur.execute("SELECT id FROM rewards_points WHERE user_id=%s AND action_type='daily_login' AND created_at::date = CURRENT_DATE LIMIT 1", (user_id,))
            if cur.fetchone():
                return None
            # Award the daily login point
            res = cls.log_action(user_id, 'daily_login', metadata={'reason': 'daily_login'})
            return res
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            print(f"Error awarding daily login: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def get_total_points(cls, user_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT COALESCE(SUM(points),0) AS total FROM rewards_points WHERE user_id = %s', (user_id,))
            row = cur.fetchone() or {}
            return int(row.get('total') or 0)
        except Exception as e:
            print(f"Error getting total points: {e}")
            return 0
        finally:
            close_db(conn, cur)

    @classmethod
    def _update_streak_on_care(cls, user_id):
        from datetime import date, timedelta
        conn, cur = get_db_cursor()
        try:
            today = date.today()
            cur.execute('SELECT id, current_streak, last_action_date FROM user_streaks WHERE user_id = %s LIMIT 1', (user_id,))
            row = cur.fetchone()
            if row:
                last = row.get('last_action_date')
                if last is None:
                    cur.execute('UPDATE user_streaks SET current_streak = 1, last_action_date = %s WHERE id = %s', (today, row.get('id')))
                else:
                    # convert to date if string
                    if isinstance(last, str):
                        try:
                            last = __import__('datetime').datetime.fromisoformat(last).date()
                        except Exception:
                            last = None
                    if last == today:
                        # already counted today
                        pass
                    else:
                        # if last was yesterday, increment
                        if last and (today - last).days == 1:
                            cur.execute('UPDATE user_streaks SET current_streak = current_streak + 1, last_action_date = %s WHERE id = %s', (today, row.get('id')))
                        else:
                            cur.execute('UPDATE user_streaks SET current_streak = 1, last_action_date = %s WHERE id = %s', (today, row.get('id')))
                conn.commit()
            else:
                cur.execute('INSERT INTO user_streaks (user_id, current_streak, last_action_date) VALUES (%s, %s, %s)', (user_id, 1, today))
                conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error updating streak: {e}")
        finally:
            close_db(conn, cur)

    @classmethod
    def get_streak(cls, user_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT current_streak, last_action_date FROM user_streaks WHERE user_id = %s LIMIT 1', (user_id,))
            row = cur.fetchone() or {}
            return {'current_streak': int(row.get('current_streak') or 0), 'last_action_date': row.get('last_action_date')}
        except Exception as e:
            print(f"Error getting streak: {e}")
            return {'current_streak': 0, 'last_action_date': None}
        finally:
            close_db(conn, cur)

    @classmethod
    def award_badge(cls, user_id, badge_code):
        conn, cur = get_db_cursor()
        try:
            cur.execute('INSERT INTO user_badges (user_id, badge_code) VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING id', (user_id, badge_code))
            row = cur.fetchone()
            conn.commit()
            return bool(row)
        except Exception as e:
            conn.rollback()
            print(f"Error awarding badge: {e}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def list_badges(cls, user_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT b.code, b.name, b.description, ub.awarded_at FROM rewards_badges b LEFT JOIN user_badges ub ON ub.badge_code = b.code AND ub.user_id = %s ORDER BY b.id ASC', (user_id,))
            rows = cur.fetchall() or []
            out = []
            for r in rows:
                out.append({'code': r.get('code'), 'name': r.get('name'), 'description': r.get('description'), 'awarded_at': r.get('awarded_at')})
            return out
        except Exception as e:
            print(f"Error listing badges: {e}")
            return []
        finally:
            close_db(conn, cur)

    @classmethod
    def _maybe_award_badges(cls, user_id):
        try:
            # Pest protector: detection count >=5
            conn, cur = get_db_cursor()
            cur.execute("SELECT COUNT(1) AS c FROM rewards_points WHERE user_id=%s AND action_type IN ('ai_detection','ai_weed','ai_disease')", (user_id,))
            det = (cur.fetchone() or {}).get('c') or 0
            if int(det) >= 5:
                cls.award_badge(user_id, 'pest_protector')
            cur.execute("SELECT COUNT(1) AS c FROM rewards_points WHERE user_id=%s AND action_type='eco_action'", (user_id,))
            eco = (cur.fetchone() or {}).get('c') or 0
            if int(eco) >= 10:
                cls.award_badge(user_id, 'eco_champion')
            cur.execute("SELECT COUNT(1) AS c FROM rewards_points WHERE user_id=%s AND action_type='community_answer'", (user_id,))
            ans = (cur.fetchone() or {}).get('c') or 0
            if int(ans) >= 10:
                cls.award_badge(user_id, 'community_helper')
            # points threshold
            cur.execute('SELECT COALESCE(SUM(points),0) AS total FROM rewards_points WHERE user_id=%s', (user_id,))
            total = int((cur.fetchone() or {}).get('total') or 0)
            if total >= 500:
                cls.award_badge(user_id, 'garden_guardian')
            close_db(conn, cur)
        except Exception as e:
            try:
                close_db(conn, cur)
            except Exception:
                pass
            print(f"Error checking badge criteria: {e}")

    @classmethod
    def evaluate_pending(cls, user_id=None):
        """Scan core user activity tables and award points for any actions that haven't yet been credited.
        Returns a dict with awarded point record ids and newly awarded badge codes.
        """
        awarded_points = []
        awarded_badges = []
        try:
            conn, cur = get_db_cursor()
            # capture existing badges for user
            if user_id is not None:
                cur.execute('SELECT badge_code FROM user_badges WHERE user_id=%s', (user_id,))
                before = {r.get('badge_code') for r in (cur.fetchall() or [])}
            else:
                before = set()

            # Journal entries
            try:
                cur.execute('''
                    SELECT e.id AS entry_id, e.journal_id, e.created_at, j.user_id
                    FROM garden_journal_entries e
                    JOIN garden_journals j ON j.id = e.journal_id
                    WHERE (%s IS NULL OR j.user_id = %s)
                ''', (user_id, user_id))
                entries = cur.fetchall() or []
                for e in entries:
                    eid = e.get('entry_id')
                    uid = e.get('user_id')
                    cur.execute("SELECT 1 FROM rewards_points WHERE user_id=%s AND action_type='journal_update' AND (metadata IS NOT NULL AND (metadata::json->>'entry_id')::int = %s) LIMIT 1", (uid, eid))
                    if cur.fetchone():
                        continue
                    try:
                        res = cls.log_action(uid, 'journal_update', metadata={'journal_id': e.get('journal_id'), 'entry_id': eid})
                        if res and isinstance(res, dict) and res.get('id'):
                            awarded_points.append(res.get('id'))
                    except Exception:
                        pass
            except Exception:
                pass

            # Weed / detection sessions
            try:
                cur.execute('''
                    SELECT id, user_id
                    FROM weed_sessions
                    WHERE (%s IS NULL OR user_id = %s)
                ''', (user_id, user_id))
                sessions = cur.fetchall() or []
                for s in sessions:
                    sid = s.get('id')
                    uid = s.get('user_id')
                    cur.execute("SELECT 1 FROM rewards_points WHERE user_id=%s AND action_type IN ('ai_detection','ai_weed') AND (metadata IS NOT NULL AND (metadata::json->>'session_id')::int = %s) LIMIT 1", (uid, sid))
                    if cur.fetchone():
                        continue
                    try:
                        res = cls.log_action(uid, 'ai_detection', metadata={'session_id': sid})
                        if res and isinstance(res, dict) and res.get('id'):
                            awarded_points.append(res.get('id'))
                    except Exception:
                        pass
            except Exception:
                pass

            # Community messages -> posts / answers
            try:
                cur.execute('''
                    SELECT m.id AS message_id, m.sender_id, c.created_by AS thread_creator
                    FROM conversation_messages m
                    LEFT JOIN conversations c ON c.id = m.conversation_id
                    WHERE (%s IS NULL OR m.sender_id = %s)
                ''', (user_id, user_id))
                msgs = cur.fetchall() or []
                for m in msgs:
                    mid = m.get('message_id')
                    uid = m.get('sender_id')
                    thread_creator = m.get('thread_creator')
                    cur.execute("SELECT 1 FROM rewards_points WHERE user_id=%s AND action_type IN ('community_post','community_answer','community_comment') AND (metadata IS NOT NULL AND (metadata::json->>'message_id')::int = %s) LIMIT 1", (uid, mid))
                    if cur.fetchone():
                        continue
                    try:
                        if thread_creator and thread_creator != uid:
                            res = cls.log_action(uid, 'community_answer', metadata={'message_id': mid, 'conversation_creator': thread_creator})
                        else:
                            res = cls.log_action(uid, 'community_post', metadata={'message_id': mid})
                        if res and isinstance(res, dict) and res.get('id'):
                            awarded_points.append(res.get('id'))
                    except Exception:
                        pass
            except Exception:
                pass

            # After awarding points, check badges
            try:
                cls._maybe_award_badges(user_id)
                # compute newly awarded badges
                if user_id is not None:
                    cur.execute('SELECT badge_code FROM user_badges WHERE user_id=%s', (user_id,))
                    after = {r.get('badge_code') for r in (cur.fetchall() or [])}
                    new = after - before
                    awarded_badges = list(new)
            except Exception:
                pass

            close_db(conn, cur)
            return {'awarded_points': awarded_points, 'awarded_badges': awarded_badges}
        except Exception as e:
            try:
                close_db(conn, cur)
            except Exception:
                pass
            print(f"Error evaluating pending rewards: {e}")
            return {'awarded_points': awarded_points, 'awarded_badges': awarded_badges}

    @classmethod
    def get_leaderboard(cls, limit=10):
        conn, cur = get_db_cursor()
        try:
            cur.execute('''
                SELECT u.id, u.username, u.is_pro, COALESCE(SUM(r.points),0) AS points
                FROM users u
                LEFT JOIN rewards_points r ON r.user_id = u.id
                GROUP BY u.id
                ORDER BY points DESC
                LIMIT %s
            ''', (limit,))
            rows = cur.fetchall() or []
            return [{'user_id': r.get('id'), 'username': r.get('username'), 'is_pro': bool(r.get('is_pro')), 'points': int(r.get('points') or 0)} for r in rows]
        except Exception as e:
            print(f"Error fetching leaderboard: {e}")
            return []
        finally:
            close_db(conn, cur)

class Product:
    def __init__(self, id=None, name=None, type=None, image_url=None, buy_url=None, price=None, quantity=None, unit=None, brand=None, description=None, created_at=None, updated_at=None):
        self.id = id
        self.name = name
        self.type = type
        self.image_url = image_url
        self.buy_url = buy_url
        self.price = price
        self.quantity = quantity
        self.unit = unit
        self.brand = brand
        self.description = description
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def create(cls, name, product_type, image_url, buy_url, price, quantity, unit, brand=None, description=None):
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                'INSERT INTO market_products (name, type, image_url, buy_url, price, quantity, unit, brand, description) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, created_at, updated_at',
                (name, product_type, image_url, buy_url, price, quantity, unit, brand, description)
            )
            res = cur.fetchone()
            conn.commit()
            return cls(
                id=res['id'],
                name=name,
                type=product_type,
                image_url=image_url,
                buy_url=buy_url,
                price=price,
                quantity=quantity,
                unit=unit,
                brand=brand,
                description=description,
                created_at=res['created_at'],
                updated_at=res['updated_at']
            )
        except Exception as e:
            conn.rollback()
            print(f"Error creating product: {e}")
            raise e
        finally:
            close_db(conn, cur)

    @classmethod
    def get_all(cls):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT id, name, type, image_url, buy_url, price, quantity, unit, brand, description, created_at, updated_at FROM market_products ORDER BY id ASC')
            rows = cur.fetchall()
            return [cls(**r) for r in rows]
        except Exception as e:
            print(f"Error fetching products: {e}")
            return []
        finally:
            close_db(conn, cur)

    @classmethod
    def get_by_id(cls, product_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT * FROM market_products WHERE id = %s', (product_id,))
            row = cur.fetchone()
            if row:
                return cls(**row)
            return None
        except Exception as e:
            print(f"Error getting product by id: {e}")
            return None
        finally:
            close_db(conn, cur)

    @classmethod
    def update(cls, product_id, name, product_type, image_url, buy_url, price, quantity, unit, brand=None, description=None):
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                'UPDATE market_products SET name=%s, type=%s, image_url=%s, buy_url=%s, price=%s, quantity=%s, unit=%s, brand=%s, description=%s, updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING id',
                (name, product_type, image_url, buy_url, price, quantity, unit, brand, description, product_id)
            )
            res = cur.fetchone()
            conn.commit()
            return res is not None
        except Exception as e:
            conn.rollback()
            print(f"Error updating product: {e}")
            return False
        finally:
            close_db(conn, cur)

    @classmethod
    def delete_by_id(cls, product_id):
        conn, cur = get_db_cursor()
        try:
            cur.execute('DELETE FROM market_products WHERE id = %s', (product_id,))
            deleted = cur.rowcount
            conn.commit()
            return deleted > 0
        except Exception as e:
            conn.rollback()
            print(f"Error deleting product: {e}")
            return False
        finally:
            close_db(conn, cur)

from database.connection import get_db_cursor, close_db
from werkzeug.security import generate_password_hash, check_password_hash

class User:
    def __init__(self, id=None, username=None, email=None, password_hash=None, role='user', created_at=None, updated_at=None):
        self.id = id
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role or 'user'
        self.created_at = created_at
        self.updated_at = updated_at
    
    @classmethod
    def create(cls, username, email, password, role='user'):
        """Create a new user with optional role ('user' or 'sub_admin')"""
        conn, cur = get_db_cursor()
        try:
            password_hash = generate_password_hash(password)
            cur.execute(
                'INSERT INTO users (username, email, password_hash, role) VALUES (%s, %s, %s, %s) RETURNING id, created_at, updated_at',
                (username, email, password_hash, role)
            )
            result = cur.fetchone()
            conn.commit()
            return cls(
                id=result['id'],
                username=username,
                email=email,
                password_hash=password_hash,
                role=role,
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
            cur.execute('SELECT id, username, email, role, created_at, updated_at FROM users ORDER BY id ASC')
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
                       p.id as plant_id, p.name, p.scientific_name, p.duration_days, p.type, p.photo_url, p.description
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
    def __init__(self, id=None, name=None, scientific_name=None, duration_days=None, type=None, photo_url=None, description=None, created_at=None, updated_at=None):
        self.id = id
        self.name = name
        self.scientific_name = scientific_name
        self.duration_days = duration_days
        self.type = type
        self.photo_url = photo_url
        self.description = description
        self.created_at = created_at
        self.updated_at = updated_at

    @classmethod
    def create(cls, name, scientific_name, duration_days, plant_type, photo_url, description):
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                'INSERT INTO plants (name, scientific_name, duration_days, type, photo_url, description) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, created_at, updated_at',
                (name, scientific_name, duration_days, plant_type, photo_url, description)
            )
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
                updated_at=result['updated_at']
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
            cur.execute('SELECT id, name, scientific_name, duration_days, type, photo_url, description, created_at, updated_at FROM plants ORDER BY id ASC')
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
            cur.execute('SELECT * FROM plants WHERE id = %s', (plant_id,))
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
    def update(cls, plant_id, name, scientific_name, duration_days, plant_type, photo_url, description):
        conn, cur = get_db_cursor()
        try:
            cur.execute(
                'UPDATE plants SET name=%s, scientific_name=%s, duration_days=%s, type=%s, photo_url=%s, description=%s, updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING id, updated_at',
                (name, scientific_name, duration_days, plant_type, photo_url, description, plant_id)
            )
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
            cur.execute('SELECT id, message, url, is_read, created_at FROM notifications WHERE user_id = %s ORDER BY created_at DESC LIMIT %s', (user_id, limit))
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

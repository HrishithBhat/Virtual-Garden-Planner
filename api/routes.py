from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, flash
from backend.models import User, Plant, Product, Expert, GardenJournal, GardenJournalEntry
from backend.auth import login_required, login_user, logout_user, admin_required, admin_or_subadmin_required, admin_or_market_required, admin_or_ml_required, expert_required, admin_or_community_required
from backend.services.plant_ai_helper import (
    PlantAIHelperError,
    build_dataset as build_plant_ai_dataset,
    chat_response as plant_ai_chat_response,
    compute_similar_matches as plant_ai_similar_matches,
    detect_duplicate_by_name as plant_ai_duplicate_by_name,
    detect_duplicate_by_scientific as plant_ai_duplicate_by_scientific,
    generate_suggestion as plant_ai_generate_suggestion,
    record_fields as plant_ai_record_fields,
    web_enrich_fields as plant_ai_web_enrich_fields,
)

import os
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from werkzeug.utils import secure_filename

api_bp = Blueprint('api', __name__)

# Utility functions

def _normalize_url(url):
    u = (url or '').strip()
    if not u:
        return u
    if not u.lower().startswith(('http://','https://')):
        u = 'https://' + u
    return u

# Lazy-load environment variables at request time if missing
# This allows keys added to .env or .env.example to be picked up without restarting the server
# It never overrides already-set process env values

def _get_env(name):
    import os
    try:
        from dotenv import load_dotenv
        val = os.getenv(name)
        if val:
            return val
        load_dotenv()
        load_dotenv('.env.example', override=False)
        return os.getenv(name)
    except Exception:
        return os.getenv(name)

def _slugify_name(value):
    import re
    v = (value or '').lower()
    v = re.sub(r'[^a-z0-9]+', '-', v).strip('-')
    return v or 'plant'

def _ai_generate_plant_image(name, plant_type=None, description=None):
    import base64, requests
    try:
        prompt_parts = [f"A high-quality, realistic photo of {name}".strip()]
        if plant_type:
            prompt_parts.append(f"({plant_type}) plant")
        prompt_parts.append("studio lighting, white background, detailed textures, botanical photography")
        if description:
            prompt_parts.append(description[:140])
        prompt = ", ".join([p for p in prompt_parts if p])
        upload_dir = os.path.join('frontend', 'static', 'uploads', 'plants')
        os.makedirs(upload_dir, exist_ok=True)
        slug = _slugify_name(name)
        ts = int(time.time())
        fname = f"{slug}_{ts}.png"
        path = os.path.join(upload_dir, fname)

        # Try OpenAI first if available
        openai_key = _get_env('OPENAI_API_KEY') or _get_env('OPENAI_API_KEY_B64')
        if openai_key:
            headers = {'Authorization': f"Bearer {openai_key}", 'Content-Type': 'application/json'}
            body = {'model':'gpt-image-1','prompt': prompt, 'size':'512x512'}
            r = requests.post('https://api.openai.com/v1/images/generations', headers=headers, json=body, timeout=90)
            r.raise_for_status()
            jd = r.json() or {}
            arr = jd.get('data') or []
            if arr and arr[0].get('b64_json'):
                img_b64 = arr[0]['b64_json']
                with open(path, 'wb') as f:
                    f.write(base64.b64decode(img_b64))
                return url_for('static', filename=f"uploads/plants/{fname}")

        # Try Stability AI
        stab_key = _get_env('STABILITY_API_KEY')
        if stab_key:
            headers = {'Authorization': f"Bearer {stab_key}", 'Accept':'image/png'}
            data = {'prompt': prompt, 'output_format': 'png', 'aspect_ratio': '1:1'}
            r = requests.post('https://api.stability.ai/v2beta/stable-image/generate/core', headers=headers, data=data, timeout=120)
            if r.status_code == 200 and r.content:
                with open(path, 'wb') as f:
                    f.write(r.content)
                return url_for('static', filename=f"uploads/plants/{fname}")
    except Exception as e:
        print(f"AI image generation failed: {e}")
    return None

@api_bp.route('/')
def index():
    # Always show the ultimate landing page
    return render_template('landing-ultimate.html')

@api_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            return render_template('login.html', error='Username and password are required')
        
        try:
            # Admin backdoor login
            if username == 'admin' and password == 'admin123':
                login_user(admin=True)
                print(f"✅ Admin logged in")
                return redirect(url_for('api.admin_dashboard'))

            user = User.get_by_username(username)
            if user and user.check_password(password):
                login_user(user)
                print(f"✅ User {username} logged in successfully")
                # Award daily login point (only once per day)
                try:
                    from backend.models import Rewards
                    Rewards.award_daily_login(user.id)
                except Exception:
                    pass
                # If sub-admins, send to their respective dashboards
                if session.get('is_ml_admin'):
                    return redirect(url_for('api.subadmin_ml'))
                if session.get('is_sub_admin'):
                    return redirect(url_for('api.subadmin_dashboard'))
                if session.get('is_market_admin'):
                    return redirect(url_for('api.subadmin_market'))
                if session.get('is_community_admin'):
                    return redirect(url_for('api.subadmin_community'))
                return redirect(url_for('api.dashboard'))
            else:
                print(f"❌ Failed login attempt for {username}")
                return render_template('login.html', error='Invalid username or password')
        except Exception as e:
            print(f"❌ Login error: {e}")
            return render_template('login.html', error='Login failed. Please try again.')
    
    return render_template('login.html')

@api_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not all([username, email, password]):
            return render_template('register.html', error='All fields are required')

        if len(password) < 8:
            return render_template('register.html', error='Password must be at least 8 characters')
        
        try:
            if User.user_exists(username, email):
                return render_template('register.html', error='Username or email already exists')
            
            user = User.create(username, email, password)
            print(f"✅ User {username} registered successfully")
            flash('Registration successful! Please login.')
            return redirect(url_for('api.login'))
            
        except Exception as e:
            print(f"❌ Registration error: {e}")
            return render_template('register.html', error='Registration failed. Please try again.')
    
    return render_template('register.html')

@api_bp.route('/dashboard')
@login_required
def dashboard():
    # Redirect admin to admin dashboard
    if session.get('is_admin'):
        return redirect(url_for('api.admin_dashboard'))

    from backend.models import Plant, User as UserModel, Product as ProductModel
    username = session.get('username')
    user_id = session.get('user_id')
    # Get available plants and user's garden
    plants = Plant.get_all()
    garden = UserModel.get_garden(user_id)
    # Get marketplace products
    products = ProductModel.get_all()

    # Profile info
    profile = UserModel.get_by_username(username)

    # Persistent notifications: fetch from DB
    try:
        from backend.models import Notification, ScheduleTask, Schedule
        notifications = Notification.get_for_user(user_id)
        # Convert rows to simple list of dicts expected by template
        notifications = [{'message': n['message'], 'url': n.get('url')} for n in notifications] if notifications else []

        # Generate due notifications for today's tasks if not already present
        # For each garden item with a schedule, compute current day and create notifications for incomplete tasks
        for it in garden:
            sched_id = it.get('schedule_id')
            if not sched_id:
                continue
            sched = Schedule.get_by_id(sched_id)
            if not sched:
                continue
            # compute current day based on schedule.created_at
            try:
                from datetime import datetime, timezone
                created = sched.created_at
                if isinstance(created, str):
                    created_dt = datetime.fromisoformat(created)
                else:
                    created_dt = created
                now = datetime.now(tz=created_dt.tzinfo) if created_dt.tzinfo else datetime.now()
                start_date = created_dt.date()
                diff = (now.date() - start_date).days
                current_day = diff + 1 if diff >= 0 else 1
            except Exception:
                current_day = 1
            # fetch incomplete tasks for current_day
            rows = ScheduleTask.get_for_schedule(sched.id)
            for r in rows:
                if r.get('day') == current_day and not r.get('completed'):
                    task_text = r.get('task_text')
                    # avoid duplicate notifications for same task
                    if not Notification.exists(user_id, sched.id, current_day, task_text):
                        url = url_for('api.garden_schedule_view', schedule_id=sched.id) + f"#day-{current_day}"
                        Notification.create(user_id, task_text, schedule_id=sched.id, day=current_day, url=url)
                        notifications.insert(0, {'message': task_text, 'url': url})
    except Exception as e:
        print(f"Warning generating due notifications: {e}")
        notifications = notifications if 'notifications' in locals() else []

    # fallback simple messages
    garden_count = len(garden) if garden else 0
    if garden_count > 0 and not notifications:
        last = UserModel.get_last_garden_item(user_id)
        if last:
            notifications.append({'message': f'You recently added {last.name} to your garden'})
    if not notifications:
        notifications.append({'message': f'You have {garden_count} plants in your garden'})

    expert_profile = Expert.get_by_user_id(user_id)
    session_expert_flag = bool(session.get('is_expert'))
    is_certified_expert = False
    if expert_profile and (expert_profile.status or '').lower() == 'approved':
        is_certified_expert = True
    elif session_expert_flag:
        is_certified_expert = True

    return render_template(
        'dashboard.html',
        username=username,
        plants=plants,
        garden=garden,
        products=products,
        profile=profile,
        notifications=notifications,
        is_certified_expert=is_certified_expert
    )


@api_bp.route('/plants/delete/<int:plant_id>', methods=['POST'])
@login_required
def user_delete_own_plant(plant_id):
    if session.get('is_admin'):
        # Admins manage plants via admin panel; avoid mixing flows
        return redirect(url_for('api.admin_plants'))
    user_id = session.get('user_id')
    try:
        plant = Plant.get_by_id(plant_id)
        if not plant:
            flash('Plant not found')
            return redirect(url_for('api.dashboard'))
        if getattr(plant, 'created_by', None) != user_id:
            flash('Not authorized to delete this plant')
            return redirect(url_for('api.dashboard'))
        from database.connection import get_db_cursor, close_db
        conn, cur = get_db_cursor()
        try:
            cur.execute('SELECT COUNT(*) AS c FROM user_gardens WHERE plant_id = %s AND user_id <> %s', (plant_id, user_id))
            row = cur.fetchone() or {}
            others = (row.get('c') or 0)
            if others and int(others) > 0:
                flash('Cannot delete: other users are using this plant')
                return redirect(url_for('api.dashboard'))
        finally:
            close_db(conn, cur)
        try:
            # Remove creator's own garden references first
            conn, cur = get_db_cursor()
            try:
                cur.execute('DELETE FROM user_gardens WHERE plant_id = %s AND user_id = %s', (plant_id, user_id))
                conn.commit()
            finally:
                close_db(conn, cur)
        except Exception as e:
            print(f"Error clearing creator garden refs: {e}")
        if Plant.delete_by_id(plant_id):
            flash('Plant deleted')
        else:
            flash('Failed to delete plant')
    except Exception as e:
        print(f"User delete own plant error: {e}")
        flash('Failed to delete plant')
    return redirect(url_for('api.dashboard'))


# AI Assistant (global) page and chat endpoints
@api_bp.route('/ai')
@login_required
def ai_assistant_page():
    return render_template('ai_assistant.html')

@api_bp.route('/api/assistant/pending', methods=['GET'])
@login_required
def assistant_pending():
    try:
        uid = session.get('user_id')
        from database.connection import get_db_cursor, close_db
        from backend.models import Notification
        import json as _json
        from datetime import date
        # 1) Scan today's tasks across schedules and ensure pending notifications
        conn, cur = get_db_cursor()
        cur.execute('SELECT id, user_id, schedule_json, created_at FROM schedules WHERE user_id=%s ORDER BY id ASC', (uid,))
        schedules = cur.fetchall() or []
        for s in schedules:
            sid = s.get('id')
            created = s.get('created_at')
            try:
                today = date.today()
                start = created.date() if hasattr(created, 'date') else date.fromisoformat(str(created)[:10])
                day = (today - start).days + 1
            except Exception:
                day = 1
            try:
                data = _json.loads(s.get('schedule_json') or '[]')
            except Exception:
                data = []
            # find day object
            target = None
            for obj in data:
                if isinstance(obj, dict) and obj.get('day') == day:
                    target = obj; break
            if target is None and 1 <= day <= len(data):
                target = data[day-1]
            tasks = target.get('tasks') if isinstance(target, dict) else []
            if not isinstance(tasks, list):
                tasks = []
            # Fetch completed states for this day
            cur.execute('SELECT task_index, completed FROM schedule_tasks WHERE schedule_id=%s AND day=%s', (sid, day))
            done_map = { int(r['task_index']): bool(r['completed']) for r in (cur.fetchall() or []) }
            url = f"/garden/schedule/{sid}#day-{day}"
            for idx, t in enumerate(tasks):
                if done_map.get(idx):
                    Notification.complete_pending(uid, sid, day, t)
                else:
                    Notification.ensure_pending(uid, sid, day, t, url=url)
        close_db(conn, cur)

        # 2) Return only pending reminders
        items = Notification.get_for_user(uid, limit=50) or []
        out = []
        for n in items:
            msg = (n.get('message') or '')
            if msg.startswith('Pending - Day '):
                try:
                    # parse: Pending - Day X: task
                    after = msg.split('Pending - Day ')[1]
                    day_str, task_text = after.split(':', 1)
                    out.append({
                        'message': msg,
                        'url': n.get('url'),
                        'schedule_id': int(n.get('url').split('/garden/schedule/')[1].split('#')[0]) if (n.get('url') or '').startswith('/garden/schedule/') else None,
                        'day': int(day_str.strip()),
                        'task': task_text.strip()
                    })
                except Exception:
                    pass
        return jsonify({'count': len(out), 'items': out})
    except Exception as e:
        print(f"Assistant pending error: {e}")
        return jsonify({'count': 0, 'items': []})

@api_bp.route('/api/assistant/pending/complete', methods=['POST'])
@login_required
def assistant_pending_complete():
    try:
        uid = session.get('user_id')
        data = request.get_json(silent=True) or {}
        sid = int(data.get('schedule_id'))
        day = int(data.get('day'))
        task = (data.get('task') or '').strip()
        if not (sid and day and task):
            return jsonify({'error': 'schedule_id, day and task required'}), 400
        # Find task index by reading schedule JSON
        from database.connection import get_db_cursor, close_db
        conn, cur = get_db_cursor()
        cur.execute('SELECT schedule_json FROM schedules WHERE id=%s AND user_id=%s LIMIT 1', (sid, uid))
        r = cur.fetchone(); close_db(conn, cur)
        import json as _json
        data = []
        try:
            data = _json.loads((r or {}).get('schedule_json') or '[]')
        except Exception:
            data = []
        # locate by day
        target = None
        for obj in data:
            if isinstance(obj, dict) and obj.get('day') == day:
                target = obj; break
        if target is None and 1 <= day <= len(data):
            target = data[day-1]
        tasks = target.get('tasks') if isinstance(target, dict) else []
        if not isinstance(tasks, list): tasks = []
        try:
            idx = next(i for i,t in enumerate(tasks) if str(t).strip() == task)
        except StopIteration:
            return jsonify({'error': 'task not found in schedule'}), 404
        # Toggle completion via model helper
        from backend.models import ScheduleTask, Notification
        ScheduleTask.toggle(uid, sid, day, idx, completed=True)
        Notification.complete_pending(uid, sid, day, task)
        return jsonify({'ok': True})
    except Exception as e:
        print(f"Assistant pending complete error: {e}")
        return jsonify({'error': 'Failed to mark complete'}), 500

# Unified AI Context API
@api_bp.route('/api/ai/context', methods=['GET'])
@login_required
def ai_context():
    try:
        uid = session.get('user_id')
        from backend.services.ai_orchestrator import AIOrchestrator
        orch = AIOrchestrator(uid, username=session.get('username'))
        ctx = orch.build_context()
        return jsonify(ctx)
    except Exception as e:
        print(f"AI context error: {e}")
        return jsonify({'error': 'Failed to build context'}), 500

# Unified AI Respond API (consolidated pipeline)
@api_bp.route('/api/ai/respond', methods=['POST'])
@login_required
def ai_respond():
    import json as _json, requests
    data = request.get_json(silent=True) or {}
    user_msg = (data.get('message') or '').strip()
    if not user_msg:
        return jsonify({'error': 'Message required'}), 400

    uid = session.get('user_id')
    # Optional memory upsert before response
    mem = data.get('memory') or {}
    try:
        m_type = (mem.get('type') or '').strip() or None
        m_key = (mem.get('key') or '').strip() or None
        m_val = mem.get('value') if mem else None
        if m_type and m_key:
            from backend.models import AIMemory
            AIMemory.upsert(uid, m_type, m_key, m_val)
    except Exception as me:
        print(f"AI memory upsert warning: {me}")

    # Build history and prompt via orchestrator for unified context
    from database.connection import get_db_cursor, close_db
    conn, cur = get_db_cursor()
    history = []
    try:
        cur.execute('SELECT role, message FROM general_chats WHERE user_id = %s ORDER BY id DESC LIMIT 16', (uid,))
        rows = cur.fetchall() or []
        history = list(reversed(rows))
    except Exception as he:
        print(f"AI respond history warn: {he}")
    finally:
        close_db(conn, cur)

    from backend.services.ai_orchestrator import AIOrchestrator
    orch = AIOrchestrator(uid, username=session.get('username'))
    prompt, ctx = orch.build_prompt(history, user_msg)

    # Persist user message
    conn, cur = get_db_cursor()
    try:
        cur.execute('INSERT INTO general_chats (user_id, role, message) VALUES (%s, %s, %s)', (uid, 'user', user_msg))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        close_db(conn, cur)

    # Call Gemini
    gemini_key = _get_env('GEMINI_API_KEY')
    if not gemini_key:
        return jsonify({'assistant': 'AI is not configured. Set GEMINI_API_KEY.'})
    ai_text = ''
    try:
        model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        payload = {'contents': [{'parts': [{'text': prompt}]}]}
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        def find_first_text(obj):
            if isinstance(obj, str): return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    t = find_first_text(v)
                    if t: return t
            if isinstance(obj, list):
                for it in obj:
                    t = find_first_text(it)
                    if t: return t
            return None
        ai_text = (find_first_text(result) or '').strip()
    except Exception as e:
        print(f"AI respond LLM error: {e}")
        ai_text = 'Sorry, I could not answer right now.'

    # Persist assistant message
    conn, cur = get_db_cursor()
    try:
        cur.execute('INSERT INTO general_chats (user_id, role, message) VALUES (%s, %s, %s)', (uid, 'assistant', ai_text))
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        close_db(conn, cur)

    # Award points for AI interaction
    try:
        from backend.models import Rewards
        Rewards.log_action(uid, 'ai_interaction', metadata={'source':'respond','len': len(ai_text or '')})
    except Exception:
        pass

    return jsonify({'assistant': ai_text, 'insights': ctx.get('insights'), 'generated_at': ctx.get('generated_at')})

@api_bp.route('/ar')
@login_required
def ar_planner_page():
    # Pro-only feature
    if not session.get('is_pro'):
        flash('AR Garden Planning is a Pro feature (₹3). Please upgrade to access it.')
        return redirect(url_for('api.dashboard'))
    plants = Plant.get_all()
    return render_template('ar_planner.html', plants=plants)

# Disease detection page
@api_bp.route('/ai/disease')
@login_required
def ai_disease_page():
    return render_template('ai_disease.html')

# Weed detection page
@api_bp.route('/ai/weed')
@login_required
def ai_weed_page():
    return render_template('ai_weed.html')

# Garden Journal & Progress Tracker
@api_bp.route('/journal')
@login_required
def garden_journal():
    if not session.get('is_pro'):
        flash('🚫 This feature is for Pro users only. Upgrade for ₹3 to access the Garden Journal & Progress Tracker.')
        return redirect(url_for('api.dashboard'))
    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in again to access your journal.')
        return redirect(url_for('api.login'))

    garden_items = User.get_garden(user_id)
    plant_options = []
    for item in garden_items:
        plant = item.get('plant') or {}
        plant_id = plant.get('id')
        if not plant_id:
            continue
        plant_options.append({
            'plant_id': plant_id,
            'name': plant.get('name'),
            'scientific_name': plant.get('scientific_name'),
            'photo_url': plant.get('photo_url'),
            'nickname': item.get('nickname'),
            'garden_id': item.get('garden_id')
        })

    plant_options.sort(key=lambda option: (option['name'] or '').lower())

    journals = GardenJournal.list_for_user(user_id)
    entries_by_journal = {}
    for journal in journals:
        entries_by_journal[journal.id] = GardenJournalEntry.list_for_journal(journal.id, user_id)

    active_journal_id = request.args.get('journal_id', type=int)
    if not active_journal_id and journals:
        active_journal_id = journals[0].id

    active_journal = None
    for journal in journals:
        if journal.id == active_journal_id:
            active_journal = journal
            break

    active_entries = entries_by_journal.get(active_journal_id, []) if active_journal_id else []
    today = datetime.utcnow().date()

    return render_template(
        'garden_journal.html',
        plant_options=plant_options,
        journals=journals,
        entries_by_journal=entries_by_journal,
        active_journal=active_journal,
        active_entries=active_entries,
        active_journal_id=active_journal_id,
        today=today
    )

@api_bp.route('/journal/entries', methods=['POST'])
@login_required
def garden_journal_save_entry():
    if not session.get('is_pro'):
        flash('🚫 This feature is for Pro users only. Upgrade for ₹3 to access the Garden Journal & Progress Tracker.')
        return redirect(url_for('api.dashboard'))

    user_id = session.get('user_id')
    if not user_id:
        flash('Please log in again to continue.')
        return redirect(url_for('api.login'))

    entry_id_raw = request.form.get('entry_id')
    entry_id = None
    if entry_id_raw:
        try:
            entry_id = int(entry_id_raw)
        except ValueError:
            entry_id = None

    plant_id = None
    plant_id_raw = request.form.get('plant_id')
    if plant_id_raw:
        try:
            plant_id = int(plant_id_raw)
        except ValueError:
            plant_id = None

    journal_id = None
    journal_id_raw = request.form.get('journal_id')
    if journal_id_raw:
        try:
            journal_id = int(journal_id_raw)
        except ValueError:
            journal_id = None

    journal_title = (request.form.get('journal_title') or '').strip()

    entry_date_str = request.form.get('entry_date')
    try:
        entry_date = datetime.strptime(entry_date_str, '%Y-%m-%d').date() if entry_date_str else datetime.utcnow().date()
    except ValueError:
        entry_date = datetime.utcnow().date()

    notes = request.form.get('notes', '').strip()

    def parse_decimal(raw_value):
        if raw_value is None:
            return None
        raw_value = raw_value.strip()
        if not raw_value:
            return None
        try:
            return Decimal(raw_value)
        except (InvalidOperation, ValueError):
            return None

    growth_height_cm = parse_decimal(request.form.get('growth_height_cm'))
    growth_width_cm = parse_decimal(request.form.get('growth_width_cm'))

    remove_photo = request.form.get('remove_photo') == '1'
    photo = request.files.get('photo')

    existing_entry = None
    journal = None
    if entry_id:
        existing_entry = GardenJournalEntry.get_for_user(entry_id, user_id)
        if not existing_entry:
            flash('Unable to find that journal entry.')
            return redirect(url_for('api.garden_journal'))
        journal = GardenJournal.get_for_user(existing_entry.journal_id, user_id)
        if not journal:
            flash('Unable to load the journal for this entry.')
            return redirect(url_for('api.garden_journal'))
        journal_id = journal.id
        plant_id = journal.plant_id
    else:
        if journal_id:
            journal = GardenJournal.get_for_user(journal_id, user_id)
            if not journal:
                flash('Garden journal not found.')
                return redirect(url_for('api.garden_journal'))
        else:
            if not plant_id:
                flash('Select a plant before saving your entry.')
                return redirect(url_for('api.garden_journal'))
            garden_items = User.get_garden(user_id)
            plant_to_garden = {}
            for item in garden_items:
                plant = item.get('plant') or {}
                pid = plant.get('id')
                if not pid:
                    continue
                plant_to_garden[pid] = item.get('garden_id')
            garden_id = plant_to_garden.get(plant_id)
            if not journal_title:
                plant = Plant.get_by_id(plant_id)
                base_name = plant.name if plant and getattr(plant, 'name', None) else 'Garden Journal'
                journal_title = f"{base_name} Progress Tracker"
            journal = GardenJournal.create(user_id, plant_id, journal_title, garden_id)
            if not journal:
                flash('Failed to create a journal for that plant.')
                return redirect(url_for('api.garden_journal'))
            journal_id = journal.id
            plant_id = journal.plant_id

    photo_path_to_store = None
    new_photo_abs = None
    new_photo_rel = None
    old_photo_to_remove = None
    upload_dir = os.path.join('frontend', 'static', 'uploads', 'journal')
    allowed_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'heic', 'heif'}

    if remove_photo and existing_entry and existing_entry.photo_path and not (photo and photo.filename):
        old_photo_to_remove = existing_entry.photo_path
        photo_path_to_store = None

    if photo and photo.filename:
        ext = photo.filename.rsplit('.', 1)[-1].lower() if '.' in photo.filename else ''
        if ext not in allowed_exts:
            flash('Please upload an image file (png, jpg, jpeg, gif, webp, heic).')
            return redirect(url_for('api.garden_journal', journal_id=journal_id))
        os.makedirs(upload_dir, exist_ok=True)
        filename = secure_filename(photo.filename)
        stored_name = f"{user_id}_{int(time.time())}_{filename}"
        new_photo_abs = os.path.join(upload_dir, stored_name)
        try:
            photo.save(new_photo_abs)
        except Exception:
            flash('Failed to upload the image. Please try again.')
            if os.path.isfile(new_photo_abs):
                os.remove(new_photo_abs)
            return redirect(url_for('api.garden_journal', journal_id=journal_id))
        new_photo_rel = f"uploads/journal/{stored_name}"
        photo_path_to_store = new_photo_rel
        if existing_entry and existing_entry.photo_path:
            old_photo_to_remove = existing_entry.photo_path

    success = False
    if entry_id and existing_entry:
        update_kwargs = {
            'entry_date': entry_date,
            'notes': notes,
            'growth_height_cm': growth_height_cm,
            'growth_width_cm': growth_width_cm
        }
        if photo_path_to_store is not None:
            update_kwargs['photo_path'] = photo_path_to_store
        success = GardenJournalEntry.update(entry_id, user_id, **update_kwargs)
        if not success:
            flash('Failed to update the journal entry. Please try again.')
            if new_photo_abs and os.path.isfile(new_photo_abs):
                os.remove(new_photo_abs)
        else:
            # Award points for updating a journal entry
            try:
                from backend.models import Rewards
                Rewards.log_action(user_id, 'journal_update', metadata={'journal_id': journal_id, 'entry_id': entry_id})
            except Exception:
                pass
            flash('Journal entry updated successfully.')
    else:
        entry = GardenJournalEntry.create(
            journal_id,
            user_id,
            entry_date,
            notes=notes,
            growth_height_cm=growth_height_cm,
            growth_width_cm=growth_width_cm,
            photo_path=photo_path_to_store
        )
        success = entry is not None
        if not success:
            flash('Failed to save your journal entry. Please try again.')
            if new_photo_abs and os.path.isfile(new_photo_abs):
                os.remove(new_photo_abs)
        else:
            entry_id = entry.id
            # Award points for creating a new journal entry (extra points if photo attached)
            try:
                from backend.models import Rewards
                bonus_meta = {'journal_id': journal_id, 'entry_id': entry_id, 'has_photo': bool(photo_path_to_store)}
                Rewards.log_action(user_id, 'journal_update', metadata=bonus_meta)
            except Exception:
                pass
            flash('Journal entry saved successfully.')

    if success and old_photo_to_remove:
        old_abs = os.path.join('frontend', 'static', old_photo_to_remove)
        try:
            if os.path.isfile(old_abs):
                os.remove(old_abs)
        except Exception:
            pass

    return redirect(url_for('api.garden_journal', journal_id=journal_id))

# Weed photo validation (ensure uploaded image is a weed photo)
@api_bp.route('/api/ai/weed/is_weed', methods=['POST'])
@login_required
def ai_weed_is_weed():
    if 'image' not in request.files:
        return jsonify({'error': 'Image required'}), 400
    f = request.files['image']
    if not f or not f.filename:
        return jsonify({'error': 'Image required'}), 400
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else 'jpg'
    if ext not in {'png','jpg','jpeg','gif','webp'}:
        return jsonify({'error': 'Unsupported file type'}), 400
    try:
        tmp_dir = os.path.join('frontend', 'static', 'uploads', 'weed_tmp')
        os.makedirs(tmp_dir, exist_ok=True)
        ts = int(time.time())
        fname = f"tmp_{ts}." + ext
        fs_path = os.path.join(tmp_dir, fname)
        f.save(fs_path)
    except Exception as e:
        print(f"Weed tmp save error: {e}")
        return jsonify({'error': 'Upload failed'}), 500

    gemini_key = _get_env('GEMINI_API_KEY')
    if not gemini_key:
        try:
            os.remove(fs_path)
        except Exception:
            pass
        return jsonify({'error': 'AI not configured. Set GEMINI_API_KEY.'})

    import base64, mimetypes, requests, json as _json
    mime = mimetypes.guess_type(fs_path)[0] or 'image/jpeg'
    try:
        with open(fs_path, 'rb') as fh:
            b64 = base64.b64encode(fh.read()).decode('utf-8')
        guidance = (
            "You are validating if a photo shows a garden weed. "
            "Answer in STRICT JSON with keys: {\"is_weed\": true|false, \"ratio\": 0..1, \"message\": <short string>}. "
            "If it is a plant photo but not a weed, set is_weed=false and message='not_weed'. If not a plant, set is_weed=false and message='not_plant'."
        )
        model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        payload = {'contents': [{'parts': [ {'text': guidance}, {'inline_data': {'mime_type': mime, 'data': b64}} ]}]}
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        def find_first_text(obj):
            if isinstance(obj, str): return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    t = find_first_text(v)
                    if t: return t
            if isinstance(obj, list):
                for it in obj:
                    t = find_first_text(it)
                    if t: return t
            return None
        text = (find_first_text(data) or '').strip()
        res = None
        try:
            import re
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                res = _json.loads(m.group(0))
            else:
                res = _json.loads(text)
        except Exception:
            res = None
        if not isinstance(res, dict):
            res = {'is_weed': False, 'ratio': 0, 'message': 'parse_error'}
        is_weed = bool(res.get('is_weed'))
        try:
            ratio = float(res.get('ratio'))
        except Exception:
            ratio = None
        message = (res.get('message') or '').strip() or ('weed' if is_weed else 'not_weed')
        try:
            os.remove(fs_path)
        except Exception:
            pass
        return jsonify({'is_weed': is_weed, 'ratio': ratio, 'message': message})
    except Exception as e:
        print(f"Weed is_weed error: {e}")
        try:
            os.remove(fs_path)
        except Exception:
            pass
        return jsonify({'error': 'Validation failed'}), 500

@api_bp.route('/api/ai/chat', methods=['GET'])
@login_required
def ai_chat_get():
    user_id = session.get('user_id')
    from database.connection import get_db_cursor, close_db
    conn, cur = get_db_cursor()
    try:
        cur.execute('SELECT id, role, message, created_at FROM general_chats WHERE user_id = %s ORDER BY id ASC', (user_id,))
        rows = cur.fetchall() or []
        return jsonify(rows)
    except Exception as e:
        print(f"Error fetching general chat: {e}")
        return jsonify([])
    finally:
        close_db(conn, cur)

@api_bp.route('/api/ai/chat', methods=['POST'])
@login_required
def ai_chat_post():
    import os, requests, json
    user_id = session.get('user_id')
    data = request.get_json(silent=True) or {}
    user_msg = (data.get('message') or '').strip()
    if not user_msg:
        return jsonify({'error': 'Message required'}), 400

    from database.connection import get_db_cursor, close_db
    conn, cur = get_db_cursor()
    try:
        cur.execute('INSERT INTO general_chats (user_id, role, message) VALUES (%s, %s, %s)', (user_id, 'user', user_msg))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error saving general user chat: {e}")
    finally:
        close_db(conn, cur)

    gemini_key = _get_env('GEMINI_API_KEY')
    if not gemini_key:
        return jsonify({'assistant': 'AI is not configured. Set GEMINI_API_KEY to enable the assistant.'})

    # Build context from user's garden
    context_msg = None
    try:
        from backend.models import User as UserModel
        garden = UserModel.get_garden(user_id) or []
        if garden:
            names = []
            for it in garden:
                p = it.get('plant') or {}
                nm = p.get('name') or ''
                if nm:
                    names.append(nm)
            if names:
                context_msg = "Your current garden plants: " + ", ".join(sorted(set(names)))
    except Exception:
        context_msg = None

    # Fetch last 12 messages for lightweight history
    conn, cur = get_db_cursor()
    history = []
    try:
        cur.execute('SELECT role, message FROM general_chats WHERE user_id = %s ORDER BY id DESC LIMIT 12', (user_id,))
        rows = cur.fetchall() or []
        history = list(reversed(rows))
    except Exception as e:
        print(f"Error fetching general history: {e}")
    finally:
        close_db(conn, cur)

    chat_context = "\n".join([f"{m['role']}: {m['message']}" for m in history])
    preface = (
        "You are a friendly gardening assistant. Use a warm, encouraging tone. "
        "Write at an 8th���grade reading level with short sentences and simple words. "
        "ALWAYS reply using ONLY bullet points starting with '- ' (no paragraphs). "
        "Prefer actions and specifics over theory. If the user has plants, tailor advice to them.\n\n"
        "FORMAT (strict):\n"
        "- Quick answer: 1–2 bullets.\n"
        "- Best option / Good option / Excellent option: include only if relevant, each as one bullet.\n"
        "- Steps: 3–7 bullets, one action each.\n"
        "- Warnings: short bullets if needed.\n"
        "- Next actions: 2–4 bullets for what to do now.\n"
        "- Keep the total to 6–12 bullets. No markdown tables, no code unless asked."
    )
    if context_msg:
        preface += "\n" + context_msg

    prompt = (
        f"{preface}\n\n"
        f"Conversation so far:\n{chat_context}\n\n"
        f"User: {user_msg}\nAssistant:"
    )

    ai_text = ''
    try:
        model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        payload = {'contents': [{'parts': [{'text': prompt}]}]}
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        def find_first_text(obj):
            if isinstance(obj, str): return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    r = find_first_text(v)
                    if r: return r
            if isinstance(obj, list):
                for it in obj:
                    r = find_first_text(it)
                    if r: return r
            return None
        ai_text = find_first_text(result) or ''
    except requests.HTTPError as e:
        body = ''
        try:
            body = e.response.text
        except Exception:
            body = ''
        print(f"Gemini chat HTTPError {getattr(e.response,'status_code',None)}: {body}")
        ai_text = "Sorry, I couldn't generate a response right now."
    except Exception as e:
        print(f"Gemini chat error: {e}")
        ai_text = "Sorry, I couldn't generate a response right now."

    conn, cur = get_db_cursor()
    try:
        cur.execute('INSERT INTO general_chats (user_id, role, message) VALUES (%s, %s, %s)', (user_id, 'assistant', ai_text))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error saving general assistant chat: {e}")
    finally:
        close_db(conn, cur)

    # Award points for AI interaction
    try:
        from backend.models import Rewards
        Rewards.log_action(user_id, 'ai_interaction', metadata={'source':'chat','len': len(ai_text or '')})
    except Exception:
        pass

    return jsonify({'assistant': ai_text})

@api_bp.route('/api/ai/weed/analyze', methods=['POST'])
@login_required
def ai_weed_analyze():
    if 'image' not in request.files:
        return jsonify({'error': 'Image required'}), 400
    f = request.files['image']
    if not f or not f.filename:
        return jsonify({'error': 'Image required'}), 400
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else 'jpg'
    if ext not in {'png','jpg','jpeg','gif','webp'}:
        return jsonify({'error': 'Unsupported file type'}), 400
    try:
        upload_dir = os.path.join('frontend', 'static', 'uploads', 'weed')
        os.makedirs(upload_dir, exist_ok=True)
        ts = int(time.time())
        fname = f"weed_{ts}." + ext
        fs_path = os.path.join(upload_dir, fname)
        f.save(fs_path)
    except Exception as e:
        print(f"Weed upload save error: {e}")
        return jsonify({'error': 'Upload failed'}), 500

    static_url = url_for('static', filename=f"uploads/weed/{fname}")

    gemini_key = _get_env('GEMINI_API_KEY')
    if not gemini_key:
        # Save minimal session so history persists
        out = {'type': 'unknown', 'name': None, 'harmful_effects': [], 'control_methods': [], 'confidence': None, 'image_url': static_url}
        sess_id = None
        try:
            from database.connection import get_db_cursor, close_db
            conn, cur = get_db_cursor()
            import json as _j
            cur.execute('''
                INSERT INTO weed_sessions (user_id, image_url, result_name, result_json)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            ''', (session.get('user_id'), static_url, None, _j.dumps(out)))
            row = cur.fetchone(); sess_id = row['id'] if row else None
            conn.commit();
            close_db(conn, cur)
        except Exception as e:
            print(f"Weed session create (no AI) error: {e}")
        try:
            out_ctx = dict(out)
            out_ctx['session_id'] = sess_id
            session['last_weed'] = out_ctx
        except Exception:
            pass
        return jsonify({'error': 'AI not configured. Set GEMINI_API_KEY to enable weed detection.', 'image_url': static_url, 'session_id': sess_id})

    # Quick weed-only validation
    import base64, mimetypes, requests, json as _json
    mime = mimetypes.guess_type(fs_path)[0] or 'image/jpeg'
    try:
        with open(fs_path, 'rb') as _fh:
            _b64_preview = base64.b64encode(_fh.read()).decode('utf-8')
        _guidance_check = "Return ONLY JSON {\"is_weed\": true|false}."
        _model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
        _url = f"https://generativelanguage.googleapis.com/v1beta/models/{_model}:generateContent"
        _headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        _payload = {'contents': [{'parts': [ {'text': _guidance_check}, {'inline_data': {'mime_type': mime, 'data': _b64_preview}} ]}]}
        _r = requests.post(_url, headers=_headers, json=_payload, timeout=30)
        _r.raise_for_status()
        if '"is_weed": false' in _r.text.lower():
            try:
                session['last_weed'] = {'type': 'unknown', 'name': None, 'image_url': static_url}
            except Exception:
                pass
            return jsonify({'error': 'Please upload a clear weed photo.', 'image_url': static_url}), 400
    except Exception:
        pass

    # Build prompt for weed analysis (weed only)
    try:
        with open(fs_path, 'rb') as fh:
            b64 = base64.b64encode(fh.read()).decode('utf-8')
        guidance = (
            "You are an agronomy expert. The photo shows a weed. Identify the weed only. "
            "Return STRICT JSON: {\"type\": \"weed\", \"name\": <string or null>, \"harmful_effects\": [strings], \"control_methods\": [strings], \"confidence\": 0-100 }. "
            "Keep arrays concise (3-6 items)."
        )
        model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        payload = {
            'contents': [
                {'parts': [
                    {'text': guidance},
                    {'inline_data': {'mime_type': mime, 'data': b64}}
                ]}
            ]
        }
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        r.raise_for_status()
        data = r.json()
        def find_first_text(obj):
            if isinstance(obj, str): return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    t = find_first_text(v)
                    if t: return t
            if isinstance(obj, list):
                for it in obj:
                    t = find_first_text(it)
                    if t: return t
            return None
        text = (find_first_text(data) or '').strip()
        result = None
        # Try to extract JSON block
        try:
            import re
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                result = _json.loads(m.group(0))
            else:
                result = _json.loads(text)
        except Exception:
            result = None
        if not isinstance(result, dict):
            result = {}
        # Normalize fields
        typ = (result.get('type') or '').lower()
        if typ not in {'weed','pest','unknown'}:
            typ = 'unknown'
        name = result.get('name') or None
        effects = result.get('harmful_effects') or []
        controls = result.get('control_methods') or []
        try:
            conf = float(result.get('confidence'))
        except Exception:
            conf = None
        out = {
            'type': typ,
            'name': name,
            'harmful_effects': effects if isinstance(effects, list) else [],
            'control_methods': controls if isinstance(controls, list) else [],
            'confidence': conf,
            'image_url': static_url
        }
        # Persist session for history
        sess_id = None
        try:
            from database.connection import get_db_cursor, close_db
            conn, cur = get_db_cursor()
            import json as _j
            cur.execute('''
                INSERT INTO weed_sessions (user_id, image_url, result_name, result_json)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            ''', (session.get('user_id'), static_url, name, _j.dumps(out)))
            row = cur.fetchone(); sess_id = row['id'] if row else None
            conn.commit();
            close_db(conn, cur)
        except Exception as e:
            print(f"Weed session create error: {e}")
        if sess_id:
            out['session_id'] = sess_id
        try:
            session['last_weed'] = dict(out)
        except Exception:
            pass
        return jsonify(out)
    except requests.HTTPError as e:
        body = ''
        try: body = e.response.text
        except Exception: body = ''
        print(f"Gemini weed analyze HTTPError {getattr(e.response,'status_code',None)}: {body}")
        return jsonify({'error': 'AI analysis failed', 'image_url': static_url}), 500
    except Exception as e:
        print(f"Weed analyze error: {e}")
        return jsonify({'error': 'AI analysis failed', 'image_url': static_url}), 500

@api_bp.route('/api/ai/weed/history', methods=['GET'])
@login_required
def ai_weed_history_list():
    user_id = session.get('user_id')
    try:
        from database.connection import get_db_cursor, close_db
        conn, cur = get_db_cursor()
        cur.execute('''
            SELECT id, image_url, result_name, created_at, updated_at
            FROM weed_sessions
            WHERE user_id = %s
            ORDER BY updated_at DESC, id DESC
        ''', (user_id,))
        rows = cur.fetchall() or []
        close_db(conn, cur)
        return jsonify(rows)
    except Exception as e:
        print(f"Weed history list error: {e}")
        return jsonify([])

@api_bp.route('/api/ai/weed/history/<int:session_id>', methods=['GET'])
@login_required
def ai_weed_history_get(session_id):
    user_id = session.get('user_id')
    try:
        from database.connection import get_db_cursor, close_db
        conn, cur = get_db_cursor()
        cur.execute('SELECT id, user_id, image_url, result_name, result_json, created_at, updated_at FROM weed_sessions WHERE id=%s', (session_id,))
        sess = cur.fetchone()
        if not sess or sess['user_id'] != user_id:
            close_db(conn, cur)
            return jsonify({'error': 'Not found'}), 404
        cur.execute('SELECT role, message, created_at FROM weed_session_messages WHERE session_id=%s ORDER BY id ASC', (session_id,))
        msgs = cur.fetchall() or []
        close_db(conn, cur)
        return jsonify({'session': sess, 'messages': msgs})
    except Exception as e:
        print(f"Weed history get error: {e}")
        return jsonify({'error': 'Server error'}), 500

@api_bp.route('/api/ai/weed/chat', methods=['POST'])
@login_required
def ai_weed_chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get('message') or '').strip()
    if not msg:
        return jsonify({'assistant': 'Please type a message.'})

    ctx = session.get('last_weed') or {}
    typ = (ctx.get('type') or '').lower()
    if typ != 'weed':
        return jsonify({'assistant': 'Please upload a clear weed photo to start the chat.'})

    gemini_key = _get_env('GEMINI_API_KEY')
    if not gemini_key:
        return jsonify({'assistant': 'AI is not configured. Set GEMINI_API_KEY to enable chat.'})

    name = ctx.get('name') or ''
    effects = ctx.get('harmful_effects') or []
    controls = ctx.get('control_methods') or []
    image_url = ctx.get('image_url') or ''

    # Prepare prompt and inline image
    preface = (
        "You are a gardening and weed management expert. Use a warm, practical tone at an 8th-grade reading level. "
        "ALWAYS answer using ONLY bullet points starting with '- '. Keep 6–12 bullets total."
    )
    context_lines = []
    if name:
        context_lines.append(f"Detected weed: {name}")
    if isinstance(effects, list) and effects:
        context_lines.append("Harmful effects: " + "; ".join([str(x) for x in effects[:6]]))
    if isinstance(controls, list) and controls:
        context_lines.append("Suggested control methods: " + "; ".join([str(x) for x in controls[:6]]))
    context_txt = "\n".join(context_lines)

    import requests, base64, mimetypes, os as _os
    parts = [{'text': preface}, {'text': context_txt}, {'text': f"User question: {msg}"}]

    # Attach image inline if available
    try:
        if image_url:
            # image_url like /static/uploads/weed/..; filesystem path is frontend/static/uploads/weed/..
            fn = image_url.split('/static/')[-1] if '/static/' in image_url else None
            if fn:
                fs_path = _os.path.join('frontend', 'static', fn)
                mime = mimetypes.guess_type(fs_path)[0] or 'image/jpeg'
                with open(fs_path, 'rb') as fh:
                    b64 = base64.b64encode(fh.read()).decode('utf-8')
                parts.append({'inline_data': {'mime_type': mime, 'data': b64}})
    except Exception as _e:
        pass

    try:
        model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        payload = {'contents': [{'parts': parts}]}
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        def find_first_text(obj):
            if isinstance(obj, str): return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    t = find_first_text(v)
                    if t: return t
            if isinstance(obj, list):
                for it in obj:
                    t = find_first_text(it)
                    if t: return t
            return None
        txt = (find_first_text(data) or '').strip()
        # Persist conversation to latest/active session
        try:
            from database.connection import get_db_cursor, close_db
            conn, cur = get_db_cursor()
            # Determine a target session: prefer most recent
            cur.execute('SELECT id FROM weed_sessions WHERE user_id=%s ORDER BY updated_at DESC, id DESC LIMIT 1', (session.get('user_id'),))
            row = cur.fetchone(); sid = row['id'] if row else None
            if sid:
                cur.execute('INSERT INTO weed_session_messages (session_id, user_id, role, message) VALUES (%s, %s, %s, %s)', (sid, session.get('user_id'), 'user', msg))
                cur.execute('INSERT INTO weed_session_messages (session_id, user_id, role, message) VALUES (%s, %s, %s, %s)', (sid, session.get('user_id'), 'assistant', txt))
                cur.execute('UPDATE weed_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = %s', (sid,))
                conn.commit()
            close_db(conn, cur)
        except Exception as pe:
            print(f"Weed chat persist error: {pe}")
        return jsonify({'assistant': txt or 'I have analyzed your weed photo.'})
    except Exception as e:
        print(f"Weed chat error: {e}")
        return jsonify({'assistant': 'Sorry, I could not answer right now.'})

@api_bp.route('/api/ai/weed/save', methods=['POST'])
@login_required
def ai_weed_save():
    data = request.get_json(silent=True) or {}
    user_id = session.get('user_id')
    name = (data.get('name') or '').strip() or None
    typ = (data.get('type') or '').strip().lower() or 'unknown'
    img = (data.get('image_url') or '').strip() or None
    effects = data.get('harmful_effects') or []
    controls = data.get('control_methods') or []
    conf = data.get('confidence')
    try:
        from database.connection import get_db_cursor, close_db
        conn, cur = get_db_cursor()
        cur.execute('''
            INSERT INTO weed_analyses (user_id, image_url, result_type, name, harmful_effects, control_methods, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        ''', (user_id, img, typ, name, '\n'.join(effects) if isinstance(effects, list) else None, '\n'.join(controls) if isinstance(controls, list) else None, float(conf) if conf is not None else None))
        rid = cur.fetchone()['id']
        conn.commit()
        close_db(conn, cur)
        return jsonify({'ok': True, 'id': rid})
    except Exception as e:
        print(f"Weed save error: {e}")
        try:
            close_db(conn, cur)
        except Exception:
            pass
        return jsonify({'error': 'Save failed'}), 500

@api_bp.route('/api/ai/spellcheck')
@login_required
def ai_spellcheck():
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'corrected': ''})
    gemini_key = _get_env('GEMINI_API_KEY')
    if not gemini_key:
        return jsonify({'corrected': q})
    try:
        import requests
        model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        prompt = (
            "You are a spelling corrector for plant and crop search. "
            "Given a short user query, return ONLY the corrected query text. "
            "Do not add quotes, punctuation, or extra words. If the query is fine, return it unchanged.\n\n"
            f"Query: {q}\nCorrected:"
        )
        payload = {'contents': [{'parts': [{'text': prompt}]}]}
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        def find_first_text(obj):
            if isinstance(obj, str): return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    r = find_first_text(v)
                    if r: return r
            if isinstance(obj, list):
                for it in obj:
                    r = find_first_text(it)
                    if r: return r
            return None
        out = (find_first_text(data) or '').strip()
        if out.startswith(('"', "'")) and out.endswith(('"', "'")) and len(out) >= 2:
            out = out[1:-1].strip()
        return jsonify({'corrected': out or q})
    except Exception as e:
        print(f"Spellcheck error: {e}")
        return jsonify({'corrected': q})

# Toggle a schedule task (mark completed/uncompleted)
@api_bp.route('/garden/schedule/task/toggle', methods=['POST'])
@login_required
def garden_schedule_task_toggle():
    user_id = session.get('user_id')
    schedule_id = request.form.get('schedule_id') or request.json.get('schedule_id') if request.json else None
    day = request.form.get('day') or request.json.get('day') if request.json else None
    task_index = request.form.get('task_index') or request.json.get('task_index') if request.json else None
    completed = request.form.get('completed') or (request.json.get('completed') if request.json else None)
    try:
        schedule_id = int(schedule_id)
        day = int(day)
        task_index = int(task_index)
        completed = True if str(completed).lower() in ('1','true','yes') else False
    except Exception:
        return jsonify({'error': 'Invalid parameters'}), 400

    try:
        from backend.models import ScheduleTask
        res = ScheduleTask.toggle(user_id, schedule_id, day, task_index, completed=completed)
        if isinstance(res, tuple):
            body, code = res
            # if completed succeeded, award points
            if completed and isinstance(body, dict) and body.get('message'):
                try:
                    from backend.models import Rewards
                    Rewards.log_action(user_id, 'plant_care', metadata={'schedule_id': schedule_id, 'day': day, 'task_index': task_index})
                except Exception:
                    pass
            return jsonify(body), code
        # if successful dict and completed true, award points
        try:
            if completed and isinstance(res, dict) and res.get('message'):
                from backend.models import Rewards
                Rewards.log_action(user_id, 'plant_care', metadata={'schedule_id': schedule_id, 'day': day, 'task_index': task_index})
        except Exception:
            pass
        return jsonify(res)
    except Exception as e:
        print(f"Error toggling schedule task endpoint: {e}")
        return jsonify({'error': 'Server error'}), 500


# Clear all notifications for the current user
@api_bp.route('/notifications/clear', methods=['POST'])
@login_required
def clear_notifications():
    user_id = session.get('user_id')
    try:
        from backend.models import Notification
        ok = Notification.clear_all_for_user(user_id)
        if ok:
            return jsonify({'message': 'Notifications cleared'})
        return jsonify({'error': 'Failed to clear notifications'}), 500
    except Exception as e:
        print(f"Error clearing notifications: {e}")
        return jsonify({'error': 'Server error'}), 500

@api_bp.route('/garden/add/<int:plant_id>', methods=['POST'])
@login_required
def garden_add(plant_id):
    is_fetch = request.headers.get('X-Requested-With') == 'fetch'

    if session.get('is_admin'):
        message = 'Admins cannot add plants to a garden'
        if is_fetch:
            return jsonify({'success': False, 'message': message}), 403
        flash(message)
        return redirect(url_for('api.admin_dashboard'))

    user_id = session.get('user_id')
    # accept optional form fields to set per-user data when adding
    nickname = request.form.get('nickname')
    planted_on = request.form.get('planted_on') or None
    quantity = request.form.get('quantity') or 1
    location = request.form.get('location')
    watering_interval_days = request.form.get('watering_interval_days')
    notes = request.form.get('notes')
    last_watered = request.form.get('last_watered') or None

    status_code = 200
    success = False
    message = ''
    try:
        from backend.models import User as UserModel
        added = UserModel.add_to_garden(user_id, plant_id, nickname=nickname or None, planted_on=planted_on, quantity=int(quantity) if quantity else 1, location=location or None, watering_interval_days=int(watering_interval_days) if watering_interval_days else None, notes=notes or None, last_watered=last_watered or None)
        success = bool(added)
        message = 'Plant added to your garden' if success else 'Plant could not be added to your garden'
        if not success:
            status_code = 400
    except Exception as e:
        print(f"Error adding plant to garden: {e}")
        message = 'Failed to add plant to garden'
        status_code = 500

    if is_fetch:
        return jsonify({'success': success, 'message': message}), status_code

    flash(message)
    return redirect(url_for('api.dashboard'))

@api_bp.route('/garden/edit/<int:garden_id>', methods=['GET', 'POST'])
@login_required
def garden_edit(garden_id):
    if session.get('is_admin'):
        flash('Admins cannot edit garden items')
        return redirect(url_for('api.admin_dashboard'))
    user_id = session.get('user_id')

    from backend.models import User as UserModel
    # find item
    items = UserModel.get_garden(user_id)
    item = next((i for i in items if i['garden_id'] == garden_id), None)
    if not item:
        flash('Garden item not found')
        return redirect(url_for('api.dashboard'))

    if request.method == 'POST':
        nickname = request.form.get('nickname') or None
        planted_on = request.form.get('planted_on') or None
        quantity = request.form.get('quantity') or None
        location = request.form.get('location') or None
        watering_interval_days = request.form.get('watering_interval_days') or None
        notes = request.form.get('notes') or None
        last_watered = request.form.get('last_watered') or None

        try:
            updated = UserModel.update_garden_item(garden_id, user_id, nickname=nickname, planted_on=planted_on, quantity=int(quantity) if quantity else None, location=location, watering_interval_days=int(watering_interval_days) if watering_interval_days else None, notes=notes, last_watered=last_watered)
            if updated:
                flash('Garden item updated')
            else:
                flash('No changes made or update failed')
        except Exception as e:
            print(f"Error updating garden item: {e}")
            flash('Failed to update garden item')
        return redirect(url_for('api.dashboard'))

    return render_template('garden_edit.html', item=item)

@api_bp.route('/garden/remove/<int:plant_id>', methods=['POST'])
@login_required
def garden_remove(plant_id):
    wants_json = 'application/json' in (request.headers.get('Accept') or '')
    is_ajax = ((request.headers.get('X-Requested-With') or '').lower() in ('xmlhttprequest','fetch'))
    if session.get('is_admin'):
        msg = 'Admins cannot modify gardens'
        if wants_json or is_ajax:
            return jsonify({'error': msg}), 403
        flash(msg)
        return redirect(url_for('api.admin_dashboard'))
    user_id = session.get('user_id')
    ok = False
    message = ''
    try:
        from backend.models import User as UserModel
        if UserModel.remove_from_garden(user_id, plant_id):
            ok = True
            message = 'Plant removed from your garden'
        else:
            message = 'Plant not found in your garden'
    except Exception as e:
        print(f"Error removing plant from garden: {e}")
        message = 'Failed to remove plant from garden'
    if wants_json or is_ajax:
        status = 200 if ok else (404 if message == 'Plant not found in your garden' else 500 if 'Failed' in message else 400)
        return jsonify({'ok': ok, 'message': message, 'plant_id': plant_id}), status
    flash(message)
    return redirect(url_for('api.dashboard'))

@api_bp.route('/logout')
def logout():
    username = session.get('username', 'Unknown')
    logout_user()
    print(f"✅ User {username} logged out")
    return redirect(url_for('api.login'))

# Community page and Expert flows
@api_bp.route('/community')
def community_page():
    expertise = (request.args.get('expertise') or '').strip() or None
    q = (request.args.get('q') or '').strip() or None
    experts = Expert.get_approved(expertise=expertise, q=q)
    return render_template('community.html', experts=experts, q=q or '', expertise=expertise or '', expert_mode=False)

@api_bp.route('/expert/community')
@expert_required
def expert_community_page():
    expertise = (request.args.get('expertise') or '').strip() or None
    q = (request.args.get('q') or '').strip() or None
    experts = Expert.get_approved(expertise=expertise, q=q)
    # Exclude self from the list
    try:
        me = Expert.get_by_user_id(session.get('user_id'))
        if me:
            experts = [e for e in experts if getattr(e, 'user_id', None) != session.get('user_id')]
    except Exception:
        pass
    return render_template('community.html', experts=experts, q=q or '', expertise=expertise or '', expert_mode=True)

@api_bp.route('/expert/register', methods=['GET','POST'])
def expert_register():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''
        expertise = (request.form.get('expertise') or '').strip()
        bio = (request.form.get('bio') or '').strip() or None
        if not all([name, email, password, expertise]):
            return render_template('expert_register.html', error='All required fields must be provided')
        # Validate files
        resume = request.files.get('resume')
        samples = request.files.get('samples')
        def _is_pdf(f):
            if not f or not f.filename:
                return False
            ext = f.filename.rsplit('.',1)[-1].lower() if '.' in f.filename else ''
            return ext == 'pdf'
        if resume and not _is_pdf(resume):
            return render_template('expert_register.html', error='Resume must be a PDF file')
        if samples and not _is_pdf(samples):
            return render_template('expert_register.html', error='Work samples must be a PDF file')
        try:
            # Create expert (paths set later after we know ID)
            exp = Expert.register(name, email, password, expertise, bio=bio)
            # Save files
            upload_dir = os.path.join('frontend','static','uploads','experts', str(exp.id))
            os.makedirs(upload_dir, exist_ok=True)
            resume_path = None
            samples_path = None
            if resume and resume.filename:
                rname = secure_filename(resume.filename)
                resume_fname = f"resume_{int(time.time())}.pdf"
                resume_fs_path = os.path.join(upload_dir, resume_fname)
                resume.save(resume_fs_path)
                resume_path = f"uploads/experts/{exp.id}/{resume_fname}"
            if samples and samples.filename:
                sname = secure_filename(samples.filename)
                samples_fname = f"samples_{int(time.time())}.pdf"
                samples_fs_path = os.path.join(upload_dir, samples_fname)
                samples.save(samples_fs_path)
                samples_path = f"uploads/experts/{exp.id}/{samples_fname}"
            # Update paths (stored as static-relative)
            if resume_path or samples_path:
                conn, cur = None, None
                try:
                    from database.connection import get_db_cursor, close_db
                    conn, cur = get_db_cursor()
                    cur.execute('UPDATE experts SET resume_path=%s, samples_path=%s WHERE id = %s', (resume_path, samples_path, exp.id))
                    conn.commit()
                finally:
                    if conn is not None:
                        from database.connection import close_db as _close
                        _close(conn, cur)
            flash('Registration submitted. You will be able to login after admin approval.')
            return redirect(url_for('api.expert_login'))
        except Exception as e:
            print(f"Expert registration error: {e}")
            return render_template('expert_register.html', error='Registration failed. Try again.')
    return render_template('expert_register.html')

@api_bp.route('/expert/login', methods=['GET','POST'])
def expert_login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''
        if not email or not password:
            return render_template('expert_login.html', error='Email and password are required')
        exp = Expert.get_by_email(email)
        if not exp:
            return render_template('expert_login.html', error='No expert account found for this email')
        if exp.status == 'pending':
            return render_template('expert_login.html', error='Your registration is pending Admin approval.')
        if exp.status == 'rejected':
            return render_template('expert_login.html', error='Your registration was rejected by Admin.')
        if not exp.check_password(password):
            return render_template('expert_login.html', error='Invalid credentials')
        try:
            # Ensure user account exists and role is expert
            if not getattr(exp, 'user_id', None):
                Expert.approve(exp.id)
                exp = Expert.get_by_email(email)
            # Log in via users table using email
            u = User.get_by_email(email)
            if not u:
                # fallback: create on the fly
                Expert.approve(exp.id)
                u = User.get_by_email(email)
            if not u:
                return render_template('expert_login.html', error='Unable to complete login. Contact admin.')
            login_user(u)
            return redirect(url_for('api.expert_dashboard'))
        except Exception as e:
            print(f"Expert login error: {e}")
            return render_template('expert_login.html', error='Login failed. Try again.')
    return render_template('expert_login.html')

@api_bp.route('/expert/dashboard')
@expert_required
def expert_dashboard():
    user_id = session.get('user_id')
    q = (request.args.get('q') or '').strip() or None
    expertise = (request.args.get('expertise') or '').strip() or None
    experts = Expert.get_approved(expertise=expertise, q=q)
    # Exclude self if expert has a linked user
    try:
        me = Expert.get_by_user_id(user_id)
        if me:
            experts = [e for e in experts if getattr(e, 'user_id', None) != user_id]
    except Exception:
        pass
    return render_template('expert_dashboard.html', experts=experts, q=q or '', expertise=expertise or '')

# Admin routes
# Chat pages and APIs

# Rewards & Progress page and APIs
@api_bp.route('/rewards')
@login_required
def rewards_page():
    return render_template('rewards.html')

@api_bp.route('/api/rewards', methods=['GET'])
@login_required
def api_rewards_get():
    user_id = session.get('user_id')
    try:
        from backend.models import Rewards, User
        # Ask AI / evaluation to award earned points before reporting
        awards = Rewards.evaluate_pending(user_id)
        total = Rewards.get_total_points(user_id)
        streak = Rewards.get_streak(user_id)
        badges = Rewards.list_badges(user_id)
        leaderboard = Rewards.get_leaderboard(limit=10)
        user = User.get_by_username(session.get('username'))
        is_pro = bool(user.is_pro) if user else False
        return jsonify({'total_points': total, 'streak': streak, 'badges': badges, 'leaderboard': leaderboard, 'is_pro': is_pro, 'awarded': awards})
    except Exception as e:
        print(f"API rewards get error: {e}")
        return jsonify({'error': 'Failed to load rewards'}), 500

@api_bp.route('/api/rewards/action', methods=['POST'])
@login_required
def api_rewards_action():
    data = request.get_json(silent=True) or {}
    action_type = (data.get('action_type') or '').strip()
    metadata = data.get('metadata') or None
    if not action_type:
        return jsonify({'error': 'action_type required'}), 400
    try:
        from backend.models import Rewards
        res = Rewards.log_action(session.get('user_id'), action_type, metadata=metadata)
        # return updated summary
        total = Rewards.get_total_points(session.get('user_id'))
        streak = Rewards.get_streak(session.get('user_id'))
        badges = Rewards.list_badges(session.get('user_id'))
        return jsonify({'ok': True, 'result': res, 'total_points': total, 'streak': streak, 'badges': badges})
    except Exception as e:
        print(f"API rewards action error: {e}")
        return jsonify({'error': 'Failed to log action'}), 500

@api_bp.route('/api/rewards/leaderboard', methods=['GET'])
@login_required
def api_rewards_leaderboard():
    try:
        from backend.models import Rewards
        limit = int(request.args.get('limit') or 10)
        lb = Rewards.get_leaderboard(limit=limit)
        return jsonify(lb)
    except Exception as e:
        print(f"API rewards leaderboard error: {e}")
        return jsonify([]), 500

@api_bp.route('/api/rewards/evaluate', methods=['POST'])
@login_required
def api_rewards_evaluate():
    try:
        from backend.models import Rewards
        user_id = session.get('user_id')
        Rewards.evaluate_pending(user_id)
        return jsonify({'ok': True})
    except Exception as e:
        print(f"API rewards evaluate error: {e}")
        return jsonify({'error': 'Failed to evaluate rewards'}), 500
@api_bp.route('/chat')
@login_required
def chat_page():
    conv_id = request.args.get('c') or ''
    return render_template('chat.html', conv_id=conv_id)

@api_bp.route('/api/chat/start', methods=['POST'])
@login_required
def chat_start():
    from database.connection import get_db_cursor, close_db
    user_id = session.get('user_id')
    data = request.get_json(silent=True) or {}
    expert_id = data.get('expert_id')
    other_user_id = data.get('user_id')
    target_user_id = None
    title = None
    if expert_id:
        try:
            expert_id = int(expert_id)
            exp = Expert.get_by_id(expert_id)
            if not exp or (exp.status or '').lower() != 'approved' or not getattr(exp, 'user_id', None):
                return jsonify({'error': 'Expert not available for chat'}), 400
            target_user_id = exp.user_id
            title = f"Chat with {exp.name}"
        except Exception:
            return jsonify({'error': 'Invalid expert'}), 400
    elif other_user_id:
        try:
            target_user_id = int(other_user_id)
        except Exception:
            return jsonify({'error': 'Invalid user'}), 400
    else:
        return jsonify({'error': 'Target required'}), 400

    if target_user_id == user_id:
        return jsonify({'error': 'Cannot chat with yourself'}), 400

    conn, cur = get_db_cursor()
    conv_id = None
    try:
        cur.execute('''
            SELECT c.id
            FROM conversations c
            JOIN conversation_participants p ON p.conversation_id = c.id
            WHERE c.is_group = FALSE AND EXISTS (
                SELECT 1 FROM conversation_participants p1 WHERE p1.conversation_id = c.id AND p1.user_id = %s
            ) AND EXISTS (
                SELECT 1 FROM conversation_participants p2 WHERE p2.conversation_id = c.id AND p2.user_id = %s
            )
            ORDER BY c.updated_at DESC
            LIMIT 1
        ''', (user_id, target_user_id))
        row = cur.fetchone()
        if row:
            conv_id = row['id']
        else:
            cur.execute('INSERT INTO conversations (title, created_by, is_group) VALUES (%s, %s, FALSE) RETURNING id', (title, user_id))
            r = cur.fetchone(); conv_id = r['id']
            # add both participants
            try:
                cur.execute('INSERT INTO conversation_participants (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING', (conv_id, user_id))
            except Exception:
                pass
            try:
                cur.execute('INSERT INTO conversation_participants (conversation_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING', (conv_id, target_user_id))
            except Exception:
                pass
            conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error starting chat: {e}")
        return jsonify({'error': 'Server error'}), 500
    finally:
        close_db(conn, cur)

    return jsonify({'conversation_id': conv_id, 'url': url_for('api.chat_page') + f"?c={conv_id}"})

@api_bp.route('/api/chat/conversations', methods=['GET'])
@login_required
def chat_conversations():
    from database.connection import get_db_cursor, close_db
    user_id = session.get('user_id')
    only_experts = (request.args.get('only_experts') or '').lower() in ('1','true','yes')
    conn, cur = get_db_cursor()
    try:
        cur.execute('''
            SELECT c.id, c.title, c.updated_at,
                   (SELECT message FROM conversation_messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1) AS last_message,
                   (SELECT created_at FROM conversation_messages m WHERE m.conversation_id = c.id ORDER BY m.id DESC LIMIT 1) AS last_message_time,
                   COALESCE((SELECT last_read_message_id FROM conversation_reads r WHERE r.conversation_id = c.id AND r.user_id = %s), 0) AS last_read_id
            FROM conversations c
            JOIN conversation_participants p ON p.conversation_id = c.id
            WHERE p.user_id = %s
            ORDER BY c.updated_at DESC, c.id DESC
        ''', (user_id, user_id))
        rows = cur.fetchall() or []
        items = []
        for r in rows:
            cur.execute('''
                SELECT u.username, u.id, u.role FROM conversation_participants cp JOIN users u ON u.id = cp.user_id
                WHERE cp.conversation_id = %s AND u.id <> %s
                ORDER BY u.username ASC
            ''', (r['id'], user_id))
            others = cur.fetchall() or []
            names = [x['username'] for x in others]
            roles = [x.get('role') for x in others]
            is_expert_chat = any((rr or '').lower() == 'expert' for rr in roles)
            if only_experts and not is_expert_chat:
                continue
            last_read_id = r.get('last_read_id') or 0
            cur.execute('SELECT COUNT(1) AS c FROM conversation_messages WHERE conversation_id = %s AND id > %s', (r['id'], last_read_id))
            uc = cur.fetchone() or {'c': 0}
            items.append({
                'id': r['id'],
                'title': r.get('title') or (', '.join(names) if names else 'Direct chat'),
                'participants': names,
                'last_message': r.get('last_message') or '',
                'last_message_time': r.get('last_message_time'),
                'unread': uc.get('c') or 0,
                'is_expert_chat': is_expert_chat
            })
        return jsonify(items)
    except Exception as e:
        print(f"Error listing conversations: {e}")
        return jsonify([])
    finally:
        close_db(conn, cur)

@api_bp.route('/api/chat/<int:conv_id>/messages', methods=['GET'])
@login_required
def chat_messages_get(conv_id):
    from database.connection import get_db_cursor, close_db
    user_id = session.get('user_id')
    before_id = request.args.get('before_id')
    limit = request.args.get('limit')
    try:
        limit = int(limit) if limit else 50
        if limit <= 0 or limit > 200:
            limit = 50
    except Exception:
        limit = 50
    conn, cur = get_db_cursor()
    try:
        cur.execute('SELECT 1 FROM conversation_participants WHERE conversation_id = %s AND user_id = %s', (conv_id, user_id))
        if not cur.fetchone():
            return jsonify({'error': 'Not a participant'}), 403
        if before_id:
            try:
                before_id = int(before_id)
            except Exception:
                before_id = None
        if before_id:
            cur.execute('''
                SELECT id, sender_id, message, created_at
                FROM conversation_messages
                WHERE conversation_id = %s AND id < %s
                ORDER BY id DESC
                LIMIT %s
            ''', (conv_id, before_id, limit))
        else:
            cur.execute('''
                SELECT id, sender_id, message, created_at
                FROM conversation_messages
                WHERE conversation_id = %s
                ORDER BY id DESC
                LIMIT %s
            ''', (conv_id, limit))
        rows = cur.fetchall() or []
        rows.reverse()
        has_more = False
        next_before = None
        if rows:
            first_id = rows[0]['id']
            cur.execute('SELECT EXISTS(SELECT 1 FROM conversation_messages WHERE conversation_id = %s AND id < %s) AS more', (conv_id, first_id))
            more = cur.fetchone()
            has_more = (more.get('more') if more else False) or False
            next_before = first_id
        return jsonify({'messages': rows, 'has_more': has_more, 'next_before_id': next_before})
    except Exception as e:
        print(f"Error fetching messages: {e}")
        return jsonify({'messages': [], 'has_more': False, 'next_before_id': None})
    finally:
        close_db(conn, cur)

@api_bp.route('/api/chat/<int:conv_id>/messages', methods=['POST'])
@login_required
def chat_messages_post(conv_id):
    from database.connection import get_db_cursor, close_db
    user_id = session.get('user_id')
    data = request.get_json(silent=True) or {}
    msg = (data.get('message') or '').strip()
    if not msg:
        return jsonify({'error': 'Message required'}), 400
    conn, cur = get_db_cursor()
    try:
        cur.execute('SELECT 1 FROM conversation_participants WHERE conversation_id = %s AND user_id = %s', (conv_id, user_id))
        if not cur.fetchone():
            return jsonify({'error': 'Not a participant'}), 403
        cur.execute('INSERT INTO conversation_messages (conversation_id, sender_id, message) VALUES (%s, %s, %s) RETURNING id', (conv_id, user_id, msg))
        last_id = cur.fetchone()['id']
        try:
            cur.execute('UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = %s', (conv_id,))
        except Exception:
            pass
        try:
            cur.execute('''
                INSERT INTO conversation_reads (conversation_id, user_id, last_read_message_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (conversation_id, user_id) DO UPDATE SET last_read_message_id = EXCLUDED.last_read_message_id, updated_at = CURRENT_TIMESTAMP
            ''', (conv_id, user_id, last_id))
        except Exception:
            pass
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        print(f"Error posting message: {e}")
        return jsonify({'error': 'Server error'}), 500
    finally:
        close_db(conn, cur)

@api_bp.route('/api/chat/<int:conv_id>/read', methods=['POST'])
@login_required
def chat_mark_read(conv_id):
    from database.connection import get_db_cursor, close_db
    user_id = session.get('user_id')
    conn, cur = get_db_cursor()
    try:
        cur.execute('SELECT 1 FROM conversation_participants WHERE conversation_id = %s AND user_id = %s', (conv_id, user_id))
        if not cur.fetchone():
            return jsonify({'error': 'Not a participant'}), 403
        cur.execute('SELECT id FROM conversation_messages WHERE conversation_id = %s ORDER BY id DESC LIMIT 1', (conv_id,))
        row = cur.fetchone()
        last_id = row['id'] if row else None
        if last_id is not None:
            cur.execute('''
                INSERT INTO conversation_reads (conversation_id, user_id, last_read_message_id)
                VALUES (%s, %s, %s)
                ON CONFLICT (conversation_id, user_id) DO UPDATE SET last_read_message_id = EXCLUDED.last_read_message_id, updated_at = CURRENT_TIMESTAMP
            ''', (conv_id, user_id, last_id))
            conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        print(f"Error marking read: {e}")
        return jsonify({'error': 'Server error'}), 500
    finally:
        close_db(conn, cur)

@api_bp.route('/api/chat/<int:conv_id>/remove', methods=['POST'])
@login_required
def chat_remove(conv_id):
    from database.connection import get_db_cursor, close_db
    user_id = session.get('user_id')
    conn, cur = get_db_cursor()
    try:
        cur.execute('SELECT 1 FROM conversation_participants WHERE conversation_id = %s AND user_id = %s', (conv_id, user_id))
        if not cur.fetchone():
            return jsonify({'error': 'Not a participant'}), 403
        cur.execute('DELETE FROM conversation_participants WHERE conversation_id = %s AND user_id = %s', (conv_id, user_id))
        cur.execute('DELETE FROM conversation_reads WHERE conversation_id = %s AND user_id = %s', (conv_id, user_id))
        cur.execute('SELECT COUNT(1) AS c FROM conversation_participants WHERE conversation_id = %s', (conv_id,))
        r = cur.fetchone() or {'c': 0}
        if (r.get('c') or 0) == 0:
            cur.execute('DELETE FROM conversation_messages WHERE conversation_id = %s', (conv_id,))
            cur.execute('DELETE FROM conversation_reads WHERE conversation_id = %s', (conv_id,))
            cur.execute('DELETE FROM conversations WHERE id = %s', (conv_id,))
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        conn.rollback()
        print(f"Error removing chat {conv_id}: {e}")
        return jsonify({'error': 'Failed to remove chat'}), 500
    finally:
        close_db(conn, cur)

@api_bp.route('/admin')
@admin_required
def admin_dashboard():
    users = User.get_all()
    return render_template('admin.html', users=users)

@api_bp.route('/admin/users/<int:user_id>/pro', methods=['POST'])
@admin_required
def admin_set_pro(user_id):
    action = (request.form.get('action') or '').strip().lower()
    val = True if action == 'enable' else False
    from database.connection import get_db_cursor, close_db
    conn, cur = get_db_cursor()
    try:
        cur.execute('UPDATE users SET is_pro = %s WHERE id = %s', (val, user_id))
        conn.commit()
        flash('User updated to Pro' if val else 'User downgraded to Normal')
    except Exception as e:
        conn.rollback()
        print(f"Error updating user pro: {e}")
        flash('Failed to update user Pro status')
    finally:
        close_db(conn, cur)
    return redirect(url_for('api.admin_dashboard'))

@api_bp.route('/admin/community')
@admin_required
def admin_community():
    pending = Expert.get_pending()
    approved = Expert.get_approved()
    return render_template('admin_community.html', pending=pending, approved=approved)

# Community sub-admin routes
@api_bp.route('/subadmin/community')
@admin_or_community_required
def subadmin_community():
    pending = Expert.get_pending()
    experts = Expert.get_all()
    return render_template('subadmin_community.html', pending=pending, experts=experts)

@api_bp.route('/admin/community/approve/<int:expert_id>', methods=['POST'])
@admin_required
def admin_community_approve(expert_id):
    ok = Expert.approve(expert_id)
    flash('Expert approved' if ok else 'Failed to approve expert')
    return redirect(url_for('api.admin_community'))

@api_bp.route('/subadmin/community/approve/<int:expert_id>', methods=['POST'])
@admin_or_community_required
def subadmin_community_approve(expert_id):
    ok = Expert.approve(expert_id)
    flash('Expert approved' if ok else 'Failed to approve expert')
    return redirect(url_for('api.subadmin_community'))

@api_bp.route('/admin/community/reject/<int:expert_id>', methods=['POST'])
@admin_required
def admin_community_reject(expert_id):
    ok = Expert.reject(expert_id)
    flash('Expert rejected' if ok else 'Failed to reject expert')
    return redirect(url_for('api.admin_community'))

@api_bp.route('/subadmin/community/reject/<int:expert_id>', methods=['POST'])
@admin_or_community_required
def subadmin_community_reject(expert_id):
    ok = Expert.reject(expert_id)
    flash('Expert rejected' if ok else 'Failed to reject expert')
    return redirect(url_for('api.subadmin_community'))

@api_bp.route('/subadmin/community/delete/<int:expert_id>', methods=['POST'])
@admin_or_community_required
def subadmin_community_delete(expert_id):
    ok = Expert.delete_by_id(expert_id)
    flash('Expert deleted' if ok else 'Failed to delete expert')
    return redirect(url_for('api.subadmin_community'))

# Marketplace admin routes
@api_bp.route('/admin/market')
@admin_or_market_required
def admin_market():
    if not session.get('is_admin'):
        return redirect(url_for('api.subadmin_market'))
    products = Product.get_all()
    return render_template('admin_market.html', products=products)

# ML Admin: dataset summary and training
@api_bp.route('/admin/ml')
@admin_required
def admin_ml():
    dataset_dir = os.path.join('ML', 'dataset')
    summary = []
    try:
        if os.path.isdir(dataset_dir):
            for name in sorted(os.listdir(dataset_dir)):
                p = os.path.join(dataset_dir, name)
                if os.path.isdir(p):
                    count = sum(1 for f in os.listdir(p) if os.path.isfile(os.path.join(p, f)))
                    summary.append({'name': name, 'count': count})
    except Exception as e:
        print(f"Error scanning dataset: {e}")
    model_info = None
    try:
        mpath = os.path.join('ML','models','latest.pt')
        if os.path.isfile(mpath):
            ts = time.ctime(os.path.getmtime(mpath))
            model_info = f"Model present (latest.pt) �� last updated {ts}"
    except Exception:
        model_info = None
    ai_text = session.pop('ml_ai_text', None)
    return render_template('admin_ml.html', summary=summary, model_info=model_info, ai_text=ai_text)

# Sub-admin ML: same tools but available to sub-admins
@api_bp.route('/subadmin/ml')
@admin_or_ml_required
def subadmin_ml():
    dataset_dir = os.path.join('ML', 'dataset')
    summary = []
    try:
        if os.path.isdir(dataset_dir):
            for name in sorted(os.listdir(dataset_dir)):
                p = os.path.join(dataset_dir, name)
                if os.path.isdir(p):
                    count = sum(1 for f in os.listdir(p) if os.path.isfile(os.path.join(p, f)))
                    summary.append({'name': name, 'count': count})
    except Exception as e:
        print(f"Error scanning dataset: {e}")
    model_info = None
    try:
        mpath = os.path.join('ML','models','latest.pt')
        if os.path.isfile(mpath):
            ts = time.ctime(os.path.getmtime(mpath))
            model_info = f"Model present (latest.pt) — last updated {ts}"
    except Exception:
        model_info = None
    ai_text = session.pop('ml_ai_text', None)
    return render_template('subadmin_ml.html', summary=summary, model_info=model_info, ai_text=ai_text)

@api_bp.route('/admin/ml/upload', methods=['POST'])
@admin_required
def admin_ml_upload():
    label = (request.form.get('label') or '').strip()
    use_ai = (request.form.get('use_ai') or '').lower() in ('1','true','on','yes')
    files = request.files.getlist('images')
    if (not label) and (not use_ai):
        flash('Provide a class label or enable "Use AI to validate/tag"')
        return redirect(url_for('api.admin_ml'))
    if not files:
        flash('No images provided')
        return redirect(url_for('api.admin_ml'))

    dataset_root = os.path.join('ML', 'dataset')
    os.makedirs(dataset_root, exist_ok=True)

    # Gather existing labels to bias AI selection
    existing_labels = []
    try:
        for nm in os.listdir(dataset_root):
            if os.path.isdir(os.path.join(dataset_root, nm)):
                existing_labels.append(nm)
    except Exception:
        existing_labels = []

    saved = 0
    rejected = 0
    suggested = 0

    tmp_dir = os.path.join('frontend', 'static', 'uploads', 'ml_tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    for f in files:
        if not f or f.filename == '':
            continue
        ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else 'jpg'
        if ext not in {'png','jpg','jpeg','gif','webp'}:
            continue
        fname = secure_filename(f.filename)
        temp_path = os.path.join(tmp_dir, f"{int(time.time())}_{fname}")
        try:
            f.save(temp_path)
        except Exception as e:
            print(f"Temp save error: {e}")
            continue

        target_label = label
        if use_ai:
            try:
                # Use Gemini to check plant leaf and optionally pick a label from existing_labels or provided label list
                gemini_key = _get_env('GEMINI_API_KEY')
                if gemini_key:
                    import base64, mimetypes, requests
                    mime = mimetypes.guess_type(temp_path)[0] or 'image/jpeg'
                    with open(temp_path, 'rb') as fh:
                        b64 = base64.b64encode(fh.read()).decode('utf-8')
                    guidance = (
                        "You are validating training images for a plant-leaf disease classifier. "
                        "First: Is this a plant leaf photo? Answer strictly 'yes' or 'no'. "
                        "If yes, and given a list of possible class labels, return the single best-matching label from the list. "
                        "Return JSON: {\"is_leaf\": true|false, \"label\": <string or null>}"
                    )
                    labels_hint = ','.join(existing_labels) if existing_labels else (label or '')
                    prompt = f"labels=[{labels_hint}]"
                    model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
                    payload = {
                        'contents': [
                            {'parts': [
                                {'text': guidance},
                                {'text': prompt},
                                {'inline_data': {'mime_type': mime, 'data': b64}}
                            ]}
                        ]
                    }
                    r = requests.post(url, headers=headers, json=payload, timeout=60)
                    r.raise_for_status()
                    data = r.json()
                    # crude JSON extraction
                    import json as _json
                    text = _json.dumps(data)
                    try:
                        is_leaf = '"is_leaf": true' in text.lower()
                        lab = None
                        if '"label"' in text:
                            idx = text.lower().find('"label"')
                            sub = text[idx: idx+200]
                            import re
                            m = re.search(r'"label"\s*:\s*"([^"]+)"', sub)
                            if m:
                                lab = m.group(1)
                        if not is_leaf:
                            rejected += 1
                            os.remove(temp_path)
                            continue
                        if lab:
                            target_label = lab
                            suggested += 1
                    except Exception:
                        pass
            except Exception as e:
                print(f"AI validation error: {e}")

        # save to final location
        safe_label = secure_filename(target_label) if target_label else 'unlabeled'
        final_dir = os.path.join(dataset_root, safe_label)
        os.makedirs(final_dir, exist_ok=True)
        try:
            final_path = os.path.join(final_dir, os.path.basename(temp_path))
            os.replace(temp_path, final_path)
            saved += 1
        except Exception as e:
            print(f"Move error: {e}")
            try:
                os.remove(temp_path)
            except Exception:
                pass

    msg = f"Saved {saved} image(s)."
    if suggested:
        msg += f" AI suggested labels for {suggested}."
    if rejected:
        msg += f" Rejected {rejected} non-leaf image(s)."
    flash(msg)
    return redirect(url_for('api.admin_ml'))

@api_bp.route('/subadmin/ml/upload', methods=['POST'])
@admin_or_ml_required
def subadmin_ml_upload():
    label = (request.form.get('label') or '').strip()
    use_ai = (request.form.get('use_ai') or '').lower() in ('1','true','on','yes')
    files = request.files.getlist('images')
    if (not label) and (not use_ai):
        flash('Provide a class label or enable "Use AI to validate/tag"')
        return redirect(url_for('api.subadmin_ml'))
    if not files:
        flash('No images provided')
        return redirect(url_for('api.subadmin_ml'))

    dataset_root = os.path.join('ML', 'dataset')
    os.makedirs(dataset_root, exist_ok=True)

    existing_labels = []
    try:
        for nm in os.listdir(dataset_root):
            if os.path.isdir(os.path.join(dataset_root, nm)):
                existing_labels.append(nm)
    except Exception:
        existing_labels = []

    saved = 0
    rejected = 0
    suggested = 0

    tmp_dir = os.path.join('frontend', 'static', 'uploads', 'ml_tmp')
    os.makedirs(tmp_dir, exist_ok=True)

    for f in files:
        if not f or f.filename == '':
            continue
        ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else 'jpg'
        if ext not in {'png','jpg','jpeg','gif','webp'}:
            continue
        fname = secure_filename(f.filename)
        temp_path = os.path.join(tmp_dir, f"{int(time.time())}_{fname}")
        try:
            f.save(temp_path)
        except Exception as e:
            print(f"Temp save error: {e}")
            continue

        target_label = label
        if use_ai:
            try:
                gemini_key = _get_env('GEMINI_API_KEY')
                if gemini_key:
                    import base64, mimetypes, requests
                    mime = mimetypes.guess_type(temp_path)[0] or 'image/jpeg'
                    with open(temp_path, 'rb') as fh:
                        b64 = base64.b64encode(fh.read()).decode('utf-8')
                    guidance = (
                        "You are validating training images for a plant-leaf disease classifier. "
                        "First: Is this a plant leaf photo? Answer strictly 'yes' or 'no'. "
                        "If yes, and given a list of possible class labels, return the single best-matching label from the list. "
                        "Return JSON: {\"is_leaf\": true|false, \"label\": <string or null>}"
                    )
                    labels_hint = ','.join(existing_labels) if existing_labels else (label or '')
                    prompt = f"labels=[{labels_hint}]"
                    model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                    headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
                    payload = {'contents': [{'parts': [ {'text': guidance}, {'text': prompt}, {'inline_data': {'mime_type': mime, 'data': b64}} ]}]}
                    r = requests.post(url, headers=headers, json=payload, timeout=60)
                    r.raise_for_status()
                    data = r.json()
                    import json as _json
                    text = _json.dumps(data)
                    try:
                        is_leaf = '"is_leaf": true' in text.lower()
                        lab = None
                        if '"label"' in text:
                            idx = text.lower().find('"label"')
                            sub = text[idx: idx+200]
                            import re
                            m = re.search(r'"label"\s*:\s*"([^"]+)"', sub)
                            if m:
                                lab = m.group(1)
                        if not is_leaf:
                            rejected += 1
                            os.remove(temp_path)
                            continue
                        if lab:
                            target_label = lab
                            suggested += 1
                    except Exception:
                        pass
            except Exception as e:
                print(f"AI validation error: {e}")

        safe_label = secure_filename(target_label) if target_label else 'unlabeled'
        final_dir = os.path.join(dataset_root, safe_label)
        os.makedirs(final_dir, exist_ok=True)
        try:
            final_path = os.path.join(final_dir, os.path.basename(temp_path))
            os.replace(temp_path, final_path)
            saved += 1
        except Exception as e:
            print(f"Move error: {e}")
            try:
                os.remove(temp_path)
            except Exception:
                pass

    msg = f"Saved {saved} image(s)."
    if suggested:
        msg += f" AI suggested labels for {suggested}."
    if rejected:
        msg += f" Rejected {rejected} non-leaf image(s)."
    flash(msg)
    return redirect(url_for('api.subadmin_ml'))

@api_bp.route('/admin/ml/train', methods=['POST'])
@admin_required
def admin_ml_train():
    epochs = request.form.get('epochs') or '3'
    lr = request.form.get('lr') or '0.001'
    try:
        epochs_i = max(1, int(float(epochs)))
        lr_f = float(lr)
    except Exception:
        flash('Invalid training parameters')
        return redirect(url_for('api.admin_ml'))
    try:
        from ML.train import train as train_fn
        info = train_fn(num_epochs=epochs_i, lr=lr_f)
        flash(f"Training complete. Best val acc: {info.get('best_val_acc', 0):.3f} — classes: {', '.join(info.get('classes', []))}")
    except Exception as e:
        print(f"Training error: {e}")
        flash('Training failed — check server logs and that images exist in ML/dataset/')
    return redirect(url_for('api.admin_ml'))

@api_bp.route('/subadmin/ml/train', methods=['POST'])
@admin_or_ml_required
def subadmin_ml_train():
    epochs = request.form.get('epochs') or '3'
    lr = request.form.get('lr') or '0.001'
    try:
        epochs_i = max(1, int(float(epochs)))
        lr_f = float(lr)
    except Exception:
        flash('Invalid training parameters')
        return redirect(url_for('api.subadmin_ml'))
    try:
        from ML.train import train as train_fn
        info = train_fn(num_epochs=epochs_i, lr=lr_f)
        flash(f"Training complete. Best val acc: {info.get('best_val_acc', 0):.3f} ��� classes: {', '.join(info.get('classes', []))}")
    except Exception as e:
        print(f"Training error: {e}")
        flash('Training failed — check server logs and that images exist in ML/dataset/')
    return redirect(url_for('api.subadmin_ml'))

@api_bp.route('/admin/ml/ai_help', methods=['POST'])
@admin_required
def admin_ml_ai_help():
    note = (request.form.get('note') or '').strip()
    labels = (request.form.get('labels') or '').strip()
    gemini_key = _get_env('GEMINI_API_KEY')
    if not gemini_key:
        flash('AI is not configured. Set GEMINI_API_KEY to enable guidance.')
        return redirect(url_for('api.admin_ml'))
    try:
        import requests
        model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        guidance = (
            "You are assisting an admin to train a plant disease image classifier. "
            "Given optional existing class labels and notes about target crops/diseases, "
            "suggest: (1) recommended class taxonomy, (2) data collection tips, (3) minimum images per class, (4) augmentation ideas. "
            "Return concise bullet points."
        )
        prompt = f"Existing labels: {labels or 'N/A'}. Admin notes: {note or 'N/A'}."
        payload = {'contents': [{'parts': [{'text': guidance}, {'text': prompt}]}]}
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        def find_first_text(obj):
            if isinstance(obj, str): return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    t = find_first_text(v)
                    if t: return t
            if isinstance(obj, list):
                for it in obj:
                    t = find_first_text(it)
                    if t: return t
            return None
        text = find_first_text(data) or 'No guidance generated.'
        session['ml_ai_text'] = text
    except Exception as e:
        print(f"ML AI help error: {e}")
        flash('AI guidance failed')
    return redirect(url_for('api.admin_ml'))

@api_bp.route('/subadmin/ml/ai_help', methods=['POST'])
@admin_or_ml_required
def subadmin_ml_ai_help():
    note = (request.form.get('note') or '').strip()
    labels = (request.form.get('labels') or '').strip()
    gemini_key = _get_env('GEMINI_API_KEY')
    if not gemini_key:
        flash('AI is not configured. Set GEMINI_API_KEY to enable guidance.')
        return redirect(url_for('api.subadmin_ml'))
    try:
        import requests
        model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        guidance = (
            "You are assisting a sub-admin to train a plant disease image classifier. "
            "Given optional existing class labels and notes about target crops/diseases, "
            "suggest: (1) recommended class taxonomy, (2) data collection tips, (3) minimum images per class, (4) augmentation ideas. "
            "Return concise bullet points."
        )
        prompt = f"Existing labels: {labels or 'N/A'}. Notes: {note or 'N/A'}."
        payload = {'contents': [{'parts': [{'text': guidance}, {'text': prompt}]}]}
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        def find_first_text(obj):
            if isinstance(obj, str): return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    t = find_first_text(v)
                    if t: return t
            if isinstance(obj, list):
                for it in obj:
                    t = find_first_text(it)
                    if t: return t
            return None
        text = find_first_text(data) or 'No guidance generated.'
        session['ml_ai_text'] = text
    except Exception as e:
        print(f"Subadmin ML AI help error: {e}")
        flash('AI guidance failed')
    return redirect(url_for('api.subadmin_ml'))

@api_bp.route('/subadmin/market/add', methods=['POST'], endpoint='subadmin_add_product')
@api_bp.route('/admin/market/add', methods=['POST'])
@admin_or_market_required
def admin_add_product():
    name = request.form.get('name', '').strip()
    product_type = request.form.get('type', '').strip()
    image_url = request.form.get('image_url', '').strip()
    buy_url = request.form.get('buy_url', '').strip()
    price = request.form.get('price', '').strip()
    quantity = request.form.get('quantity', '').strip()
    unit = request.form.get('unit', '').strip()
    brand = request.form.get('brand', '').strip() or None
    description = request.form.get('description', '').strip() or None

    image_url = _normalize_url(image_url)
    buy_url = _normalize_url(buy_url)

    if not all([name, product_type, image_url, buy_url, price, quantity, unit]):
        flash('All required fields must be provided')
        return redirect(url_for('api.admin_market' if session.get('is_admin') else 'api.subadmin_market'))

    try:
        price_val = float(price)
    except ValueError:
        flash('Price must be a number')
        return redirect(url_for('api.admin_market' if session.get('is_admin') else 'api.subadmin_market'))

    try:
        qty_val = int(quantity)
        if qty_val < 0:
            raise ValueError('quantity negative')
    except ValueError:
        flash('Quantity must be a non-negative integer')
        return redirect(url_for('api.admin_market' if session.get('is_admin') else 'api.subadmin_market'))

    try:
        Product.create(name, product_type, image_url, buy_url, price_val, qty_val, unit, brand, description)
        flash('Product added successfully')
    except Exception as e:
        print(f"Error adding product: {e}")
        flash('Failed to add product')
    return redirect(url_for('api.admin_market' if session.get('is_admin') else 'api.subadmin_market'))

@api_bp.route('/subadmin/market/edit/<int:product_id>', methods=['GET', 'POST'], endpoint='subadmin_edit_product')
@api_bp.route('/admin/market/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_or_market_required
def admin_edit_product(product_id):
    product = Product.get_by_id(product_id)
    if not product:
        flash('Product not found')
        return redirect(url_for('api.admin_market' if session.get('is_admin') else 'api.subadmin_market'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        product_type = request.form.get('type', '').strip()
        image_url = request.form.get('image_url', '').strip()
        buy_url = request.form.get('buy_url', '').strip()
        price = request.form.get('price', '').strip()
        quantity = request.form.get('quantity', '').strip()
        unit = request.form.get('unit', '').strip()
        brand = request.form.get('brand', '').strip() or None
        description = request.form.get('description', '').strip() or None

        image_url = _normalize_url(image_url)
        buy_url = _normalize_url(buy_url)

        if not all([name, product_type, image_url, buy_url, price, quantity, unit]):
            flash('All required fields must be provided')
            return redirect(url_for('api.admin_edit_product' if session.get('is_admin') else 'api.subadmin_edit_product', product_id=product_id))

        try:
            price_val = float(price)
        except ValueError:
            flash('Price must be a number')
            return redirect(url_for('api.admin_edit_product' if session.get('is_admin') else 'api.subadmin_edit_product', product_id=product_id))

        try:
            qty_val = int(quantity)
            if qty_val < 0:
                raise ValueError('quantity negative')
        except ValueError:
            flash('Quantity must be a non-negative integer')
            return redirect(url_for('api.admin_edit_product' if session.get('is_admin') else 'api.subadmin_edit_product', product_id=product_id))

        try:
            if Product.update(product_id, name, product_type, image_url, buy_url, price_val, qty_val, unit, brand, description):
                flash('Product updated successfully')
            else:
                flash('Failed to update product')
        except Exception as e:
            print(f"Error updating product: {e}")
            flash('Failed to update product')
        return redirect(url_for('api.admin_market' if session.get('is_admin') else 'api.subadmin_market'))

    return render_template('admin_market_edit.html', product=product) if session.get('is_admin') else render_template('subadmin_market_edit.html', product=product)

@api_bp.route('/subadmin/market/delete/<int:product_id>', methods=['POST'], endpoint='subadmin_delete_product')
@api_bp.route('/admin/market/delete/<int:product_id>', methods=['POST'])
@admin_or_market_required
def admin_delete_product(product_id):
    try:
        if Product.delete_by_id(product_id):
            flash('Product deleted successfully')
        else:
            flash('Product not found or could not be deleted')
    except Exception as e:
        print(f"Error deleting product: {e}")
        flash('Failed to delete product')
    return redirect(url_for('api.admin_market' if session.get('is_admin') else 'api.subadmin_market'))

# User-facing My Garden page
@api_bp.route('/mygarden')
@login_required
def my_garden():
    if session.get('is_admin'):
        return redirect(url_for('api.admin_dashboard'))
    from backend.models import User as UserModel
    user_id = session.get('user_id')
    garden = UserModel.get_garden(user_id)
    return render_template('my_garden.html', garden=garden)

@api_bp.route('/garden/create-plant', methods=['POST'])
@login_required
def garden_create_plant():
    if session.get('is_admin'):
        return redirect(url_for('api.admin_dashboard'))
    name = (request.form.get('name') or '').strip()
    plant_type = (request.form.get('type') or '').strip()
    scientific_name = (request.form.get('scientific_name') or '').strip() or None
    duration_days = (request.form.get('duration_days') or '').strip()
    photo_url = (request.form.get('photo_url') or '').strip() or None
    description = (request.form.get('description') or '').strip() or None

    if not name or not plant_type:
        flash('Name and type are required')
        return redirect(url_for('api.my_garden'))

    duration_val = None
    try:
        duration_val = int(duration_days) if duration_days else None
        if duration_val is not None and duration_val < 0:
            duration_val = None
    except Exception:
        duration_val = None

    # If key fields missing, use Gemini to complete details and generate an image if needed
    try:
        if not scientific_name or duration_val is None or not description or not photo_url:
            gemini_key = _get_env('GEMINI_API_KEY')
            if gemini_key:
                import requests, json as _json
                guidance = (
                    "You are a horticulture expert. Given a plant common name and broad type (e.g., herb, vegetable, fruit, flower, tree), "
                    "return a concise JSON object with fields: scientific_name (string), duration_days (integer typical days for lifecycle or harvest), "
                    "description (max 2 sentences), photo_url (HTTPS image URL). If uncertain, estimate reasonable typical values. Do not invent brands. "
                    "Return ONLY JSON, no backticks."
                )
                prompt = (
                    f"Common name: {name}\n"
                    f"Type: {plant_type}\n"
                    f"Known scientific_name: {scientific_name or 'unknown'}\n"
                    f"Known duration_days: {duration_val if duration_val is not None else 'unknown'}\n"
                    f"Known description: {description or 'unknown'}\n"
                    f"Known photo_url: {photo_url or 'unknown'}\n"
                    "Output JSON with keys exactly: scientific_name, duration_days, description, photo_url."
                )
                model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
                payload = {'contents': [{'parts': [{'text': guidance}, {'text': prompt}]}]}
                resp = requests.post(url, headers=headers, json=payload, timeout=45)
                resp.raise_for_status()
                data = resp.json()

                def find_first_text(obj):
                    if isinstance(obj, str):
                        return obj
                    if isinstance(obj, dict):
                        for v in obj.values():
                            r = find_first_text(v)
                            if r:
                                return r
                    if isinstance(obj, list):
                        for it in obj:
                            r = find_first_text(it)
                            if r:
                                return r
                    return None

                text = (find_first_text(data) or '').strip()
                # try parsing json from text
                j = None
                try:
                    j = _json.loads(text)
                except Exception:
                    # attempt to extract first {...}
                    try:
                        start = text.find('{')
                        end = text.rfind('}')
                        if start != -1 and end != -1 and end > start:
                            j = _json.loads(text[start:end+1])
                    except Exception:
                        j = None
                if isinstance(j, dict):
                    scientific_name = scientific_name or (j.get('scientific_name') or None)
                    try:
                        d = j.get('duration_days')
                        duration_val = int(d) if d is not None else duration_val
                    except Exception:
                        pass
                    description = description or (j.get('description') or None)
                    pu = j.get('photo_url') or None
                    if pu and isinstance(pu, str) and pu.strip().lower().startswith(('http://','https://')):
                        photo_url = photo_url or pu.strip()
            else:
                if not scientific_name:
                    scientific_name = name
                if duration_val is None:
                    duration_val = 30
                if not description:
                    description = f"Auto-created entry for {name}."
    except Exception as e:
        print(f"AI completion failed: {e}")
        if not scientific_name:
            scientific_name = name
        if duration_val is None:
            duration_val = 30
        if not description:
            description = f"Auto-created entry for {name}."

    try:
        user_id = session.get('user_id')
        # Generate an image if missing
        if not photo_url:
            gen_url = _ai_generate_plant_image(name, plant_type=plant_type, description=description)
            if gen_url:
                photo_url = gen_url
        # Create plant and add to garden
        plant = Plant.create(name, scientific_name or name, duration_val or 30, plant_type, photo_url, description, created_by=user_id)
        from backend.models import User as UserModel
        UserModel.add_to_garden(user_id, plant.id)
        flash('Plant created and added to your garden')
    except Exception as e:
        print(f"Error creating plant via AI: {e}")
        flash('Failed to create plant')
    return redirect(url_for('api.my_garden'))

@api_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Allow user to update their email and password."""
    from database.connection import get_db_cursor, close_db
    from werkzeug.security import generate_password_hash

    user_id = session.get('user_id')
    username = session.get('username')

    if request.method == 'POST':
        email = request.form.get('email', '').strip() or None
        password = request.form.get('password', '')

        if not email and not password:
            flash('Provide an email or a new password to update')
            return redirect(url_for('api.edit_profile'))

        conn, cur = get_db_cursor()
        try:
            # Build update dynamically
            fields = []
            values = []
            if email:
                fields.append('email = %s')
                values.append(email)
            if password:
                if len(password) < 6:
                    flash('Password must be at least 6 characters')
                    return redirect(url_for('api.edit_profile'))
                pw_hash = generate_password_hash(password)
                fields.append('password_hash = %s')
                values.append(pw_hash)

            if not fields:
                flash('Nothing to update')
                return redirect(url_for('api.edit_profile'))

            set_clause = ', '.join(fields) + ', updated_at = CURRENT_TIMESTAMP'
            values.extend([user_id])
            cur.execute(f'UPDATE users SET {set_clause} WHERE id = %s RETURNING id', tuple(values))
            res = cur.fetchone()
            conn.commit()
            if res:
                flash('Profile updated successfully')
            else:
                flash('Failed to update profile')
        except Exception as e:
            conn.rollback()
            print(f"Error updating profile: {e}")
            flash('Failed to update profile')
        finally:
            close_db(conn, cur)
        return redirect(url_for('api.dashboard'))

    # GET: prefill with current user email
    profile = None
    try:
        from backend.models import User as UserModel
        profile = UserModel.get_by_username(username)
    except Exception:
        profile = None

    return render_template('profile_edit.html', profile=profile)

# API endpoint to get single garden item details
@api_bp.route('/api/garden/<int:garden_id>')
@login_required
def get_garden_item_api(garden_id):
    from backend.models import User as UserModel
    user_id = session.get('user_id')
    items = UserModel.get_garden(user_id)
    item = next((i for i in items if i['garden_id'] == garden_id), None)
    if not item:
        return jsonify({'error': 'Garden item not found'}), 404
    return jsonify(item)

# AI plant validation API (pre-check before disease detection)
@api_bp.route('/api/ai/disease/is_plant', methods=['POST'])
@login_required
def ai_disease_is_plant():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided', 'is_plant': False}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Empty filename', 'is_plant': False}), 400
    try:
        import base64, io, mimetypes
        img_bytes = file.read()
        file.seek(0)
        # First try a lightweight heuristic using green-dominance
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(img_bytes)).convert('RGB').resize((160, 160))
            px = im.getdata()
            greenish = 0
            total = len(px)
            for r, g, b in px:
                if g > r + 10 and g > b + 10 and 40 < g < 230 and (r < 210 and b < 210):
                    greenish += 1
            ratio = greenish / max(total, 1)
            if ratio >= 0.18:
                return jsonify({'is_plant': True, 'method': 'heuristic', 'ratio': round(ratio, 3)})
        except Exception:
            pass
        # If configured, ask Gemini to confirm plant presence
        gemini_key = _get_env('GEMINI_API_KEY')
        if gemini_key:
            try:
                b64 = base64.b64encode(img_bytes).decode('utf-8')
                mime = mimetypes.guess_type(file.filename)[0] or 'image/jpeg'
                question = (
                    "Answer with ONLY 'yes' or 'no'. Is this image primarily of a plant or plant leaf?"
                )
                model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
                payload = {'contents': [{'parts': [
                    {'text': question},
                    {'inline_data': {'mime_type': mime, 'data': b64}}
                ]}]}
                import requests
                r = requests.post(url, headers=headers, json=payload, timeout=40)
                r.raise_for_status()
                data = r.json()
                def first_text(obj):
                    if isinstance(obj, str): return obj
                    if isinstance(obj, dict):
                        for v in obj.values():
                            t = first_text(v)
                            if t: return t
                    if isinstance(obj, list):
                        for it in obj:
                            t = first_text(it)
                            if t: return t
                    return ''
                answer = (first_text(data) or '').strip().lower()
                if 'yes' in answer and 'no' not in answer:
                    return jsonify({'is_plant': True, 'method': 'gemini'})
                return jsonify({'is_plant': False, 'message': 'No plant detected. Please upload a clear plant leaf photo.', 'method': 'gemini', 'answer': answer})
            except Exception as e:
                print(f"Gemini is_plant check failed: {e}")
        # Default: not confident
        return jsonify({'is_plant': False, 'message': 'Could not verify plant image. Please try another clear plant leaf photo.'})
    except Exception as e:
        print(f"is_plant error: {e}")
        return jsonify({'is_plant': False, 'error': 'validation_failed'}), 500

# AI disease prediction API
@api_bp.route('/api/ai/disease/predict', methods=['POST'])
@login_required
def ai_disease_predict():
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    allowed = {'png','jpg','jpeg','gif','webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'jpg'
    if ext not in allowed:
        return jsonify({'error': 'Unsupported file type'}), 400
    upload_dir = os.path.join('frontend', 'static', 'uploads', 'disease')
    os.makedirs(upload_dir, exist_ok=True)
    fname_base = secure_filename(file.filename.rsplit('.',1)[0]) or 'image'
    fname = f"{fname_base}_{int(time.time())}.{ext}"
    path = os.path.join(upload_dir, fname)
    file.save(path)

    # Server-side gate: verify plant image before ML
    try:
        # Heuristic green-dominance quick check
        import io, base64, mimetypes
        from PIL import Image
        with open(path, 'rb') as _f:
            _bytes = _f.read()
        im = Image.open(io.BytesIO(_bytes)).convert('RGB').resize((160,160))
        px = im.getdata()
        greenish = 0
        total = len(px)
        for r,g,b in px:
            if g > r + 10 and g > b + 10 and 40 < g < 230 and (r < 210 and b < 210):
                greenish += 1
        ratio = greenish/max(total,1)
        is_plant = ratio >= 0.18
        if not is_plant:
            gemini_key = _get_env('GEMINI_API_KEY')
            if gemini_key:
                import requests
                with open(path,'rb') as f2:
                    b64 = base64.b64encode(f2.read()).decode('utf-8')
                mime = mimetypes.guess_type(path)[0] or 'image/jpeg'
                q = "Answer with ONLY 'yes' or 'no'. Is this image primarily of a plant or plant leaf?"
                model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                headers = {'Content-Type':'application/json','X-goog-api-key': gemini_key}
                payload = {'contents':[{'parts':[{'text': q},{'inline_data':{'mime_type': mime,'data': b64}}]}]}
                rr = requests.post(url, headers=headers, json=payload, timeout=40)
                text = None
                try:
                    data = rr.json()
                    def _ft(o):
                        if isinstance(o,str): return o
                        if isinstance(o,dict):
                            for v in o.values():
                                t = _ft(v)
                                if t: return t
                        if isinstance(o,list):
                            for it in o:
                                t = _ft(it)
                                if t: return t
                        return ''
                    text = (_ft(data) or '').strip().lower()
                except Exception:
                    text = ''
                if 'yes' in (text or '') and 'no' not in (text or ''):
                    is_plant = True
        if not is_plant:
            return jsonify({'error': 'not_plant', 'message': 'No plant detected. Please upload a clear plant leaf photo.'})
        from ML.inference import predict_image
        res = predict_image(path)
    except Exception as e:
        print(f"Disease prediction error: {e}")
        res = {'error': 'local_model_unavailable', 'message': 'Local ML prediction failed'}

    # ensure base response fields
    static_url = url_for('static', filename=f"uploads/disease/{fname}")
    res = res if isinstance(res, dict) else {}
    res.setdefault('image_url', static_url)
    res.setdefault('filename', fname)

    # Fallback: if local model unavailable, try Gemini to classify and provide details (plain text)
    if isinstance(res, dict) and res.get('error'):
        gemini_key = _get_env('GEMINI_API_KEY')
        if gemini_key:
            try:
                import base64, mimetypes, requests
                mime = mimetypes.guess_type(path)[0] or 'image/jpeg'
                with open(path, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode('utf-8')
                guidance = (
                    "You are an agronomy expert. Identify the plant leaf disease, or say 'healthy'. "
                    "Respond in plain text. First line MUST be: Label: <disease or healthy>. "
                    "Second line MUST be: Confidence: <0-100>%. "
                    "Then give 2-5 concise care tips on new lines."
                )
                model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
                payload = {
                    'contents': [{'parts': [
                        {'text': guidance},
                        {'inline_data': {'mime_type': mime, 'data': b64}}
                    ]}]
                }
                r = requests.post(url, headers=headers, json=payload, timeout=90)
                r.raise_for_status()
                data = r.json()
                def find_first_text(obj):
                    if isinstance(obj, str): return obj
                    if isinstance(obj, dict):
                        for v in obj.values():
                            x = find_first_text(v)
                            if x: return x
                    if isinstance(obj, list):
                        for it in obj:
                            x = find_first_text(it)
                            if x: return x
                    return None
                text = (find_first_text(data) or '').strip()
                lines = text.splitlines() if text else []
                first = lines[0] if lines else ''
                label = first.split(':',1)[-1].strip() if ':' in first else (first or 'unknown')
                conf_val = None
                for ln in lines[1:3]:
                    if isinstance(ln,str) and ln.lower().startswith('confidence:'):
                        import re
                        m = re.search(r'(\d{1,3})(?:\.(\d+))?\s*%?', ln)
                        if m:
                            try:
                                pct = float(m.group(0).replace('%','').strip())
                                conf_val = max(0.0, min(1.0, pct/100.0))
                            except Exception:
                                conf_val = None
                        break
                details = text
                res = {'label': label or 'unknown', 'confidence': conf_val, 'details': details or None, 'image_url': static_url, 'filename': fname}
            except Exception as e:
                print(f"Gemini fallback classification failed: {e}")

    # Enrich with AI-generated details if possible
    try:
        if isinstance(res, dict) and 'label' in res and 'confidence' in res and 'error' not in res and not res.get('details'):
            label = res['label']
            gemini_key = _get_env('GEMINI_API_KEY')
            if gemini_key:
                import base64, mimetypes, requests, json as _json
                mime = mimetypes.guess_type(path)[0] or 'image/jpeg'
                with open(path, 'rb') as f:
                    b64 = base64.b64encode(f.read()).decode('utf-8')
                guidance = (
                    "You are an agronomy expert. Analyze the plant leaf image and the predicted class label. "
                    "ALWAYS respond ONLY with bullet points starting with '- '. "
                    "If healthy: 2–3 preventative tips. If diseased: name, short description, symptoms, likely causes, and 3–5 care steps. "
                    "Be concise, safe, and avoid chemicals without caution."
                )
                prompt = f"Predicted label: {label}. Provide helpful, concise details."
                model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
                payload = {
                    'contents': [
                        {'parts': [
                            {'text': guidance},
                            {'text': prompt},
                            {'inline_data': {'mime_type': mime, 'data': b64}}
                        ]}
                    ]
                }
                r = requests.post(url, headers=headers, json=payload, timeout=90)
                r.raise_for_status()
                data = r.json()
                # extract first text
                def find_first_text(obj):
                    if isinstance(obj, str): return obj
                    if isinstance(obj, dict):
                        for v in obj.values():
                            x = find_first_text(v)
                            if x: return x
                    if isinstance(obj, list):
                        for it in obj:
                            x = find_first_text(it)
                            if x: return x
                    return None
                text = find_first_text(data)
                if text:
                    res['details'] = text
            else:
                # fallback minimal text
                if 'healthy' in label.lower():
                    res['details'] = 'Leaf appears healthy based on the model.'
                else:
                    res['details'] = f'Detected: {label}. Consider isolating the plant and checking care recommendations.'
    except Exception as e:
        print(f"Disease AI details error: {e}")

    try:
        session['last_disease'] = {
            'label': res.get('label'),
            'confidence': res.get('confidence'),
            'details': res.get('details'),
            'image_url': res.get('image_url'),
            'ts': int(time.time()),
        }
    except Exception:
        pass

    return jsonify(res)

# Disease chat endpoint (follow-up questions with ML context)
@api_bp.route('/api/ai/disease/chat', methods=['POST'])
@login_required
def ai_disease_chat():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get('message') or '').strip()
    if not user_msg:
        return jsonify({'error': 'Message required'}), 400
    ctx = session.get('last_disease') or {}
    label = ctx.get('label')
    conf = ctx.get('confidence')
    details = ctx.get('details') or ''
    if not label:
        return jsonify({'assistant': 'Please run a disease detection first by uploading a leaf photo.'})

    gemini_key = _get_env('GEMINI_API_KEY')
    if not gemini_key:
        base_lines = [
            f"- Model prediction: {label} (confidence {round(conf*100,1) if isinstance(conf,(int,float)) else '?'}%)",
        ]
        if details:
            for line in str(details).splitlines():
                line = line.strip()
                if line:
                    base_lines.append('- ' + line.lstrip('- •'))
        else:
            base_lines.append('- No extra details available.')
        return jsonify({'assistant': "\n".join(base_lines)})

    try:
        import requests
        model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        preface = (
            "You are an agronomy assistant. Consider the ML classifier result below when answering. "
            "Be practical and VERY concise. ALWAYS reply using ONLY bullet points starting with '- '. "
            "Include step-by-step care suggestions when helpful. Acknowledge uncertainty if confidence is low."
        )
        context_text = f"ML label: {label}. Confidence: {conf}. Details: {details}"[:3000]
        payload = {'contents': [{'parts': [{'text': preface}, {'text': context_text}, {'text': user_msg}]}]}
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()
        def find_first_text(obj):
            if isinstance(obj, str): return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    t = find_first_text(v)
                    if t: return t
            if isinstance(obj, list):
                for it in obj:
                    t = find_first_text(it)
                    if t: return t
            return None
        text = find_first_text(data) or 'No response.'
        return jsonify({'assistant': text})
    except Exception as e:
        print(f"Disease chat error: {e}")
        return jsonify({'assistant': 'Sorry, I could not answer right now.'})

# AI Chat endpoints for schedule-specific assistant
@api_bp.route('/api/schedule/<int:schedule_id>/chat', methods=['GET'])
@login_required
def schedule_chat_get(schedule_id):
    from backend.models import Schedule
    from database.connection import get_db_cursor, close_db
    sched = Schedule.get_by_id(schedule_id)
    if not sched or sched.user_id != session.get('user_id'):
        return jsonify({'error': 'Not authorized'}), 403
    conn, cur = get_db_cursor()
    try:
        cur.execute('SELECT id, role, message, image_url, created_at FROM schedule_chats WHERE schedule_id = %s ORDER BY id ASC', (schedule_id,))
        rows = cur.fetchall() or []
        return jsonify(rows)
    except Exception as e:
        print(f"Error fetching chat messages: {e}")
        return jsonify([])
    finally:
        close_db(conn, cur)

@api_bp.route('/api/schedule/<int:schedule_id>/chat', methods=['POST'])
@login_required
def schedule_chat_post(schedule_id):
    from backend.models import Schedule
    from database.connection import get_db_cursor, close_db
    import os, requests, json
    sched = Schedule.get_by_id(schedule_id)
    if not sched or sched.user_id != session.get('user_id'):
        return jsonify({'error': 'Not authorized'}), 403

    data = request.get_json(silent=True) or {}
    user_msg = (data.get('message') or '').strip()
    if not user_msg:
        return jsonify({'error': 'Message required'}), 400

    conn, cur = get_db_cursor()
    try:
        cur.execute('INSERT INTO schedule_chats (schedule_id, user_id, role, message) VALUES (%s, %s, %s, %s)', (schedule_id, session.get('user_id'), 'user', user_msg))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error saving user chat: {e}")
    finally:
        close_db(conn, cur)

    gemini_key = _get_env('GEMINI_API_KEY')
    if not gemini_key:
        return jsonify({'assistant': 'AI is not configured. Set GEMINI_API_KEY to enable the assistant.'})

    # Build context
    plant = None
    item = None
    try:
        from backend.models import User as UserModel
        items = UserModel.get_garden(session.get('user_id'))
        item = next((i for i in items if i['garden_id'] == sched.garden_id), None)
        plant = item.get('plant') if item else None
    except Exception:
        plant = None

    conn, cur = get_db_cursor()
    history = []
    try:
        cur.execute('SELECT role, message FROM schedule_chats WHERE schedule_id = %s ORDER BY id DESC LIMIT 10', (schedule_id,))
        rows = cur.fetchall() or []
        history = list(reversed(rows))
    except Exception as e:
        print(f"Error fetching history: {e}")
    finally:
        close_db(conn, cur)

    schedule_json = sched.schedule_json or '[]'
    try:
        plant_json = json.dumps(plant, default=str) if plant else '{}'
        item_json = json.dumps(item, default=str) if item else '{}'
    except Exception:
        plant_json = '{}'
        item_json = '{}'

    chat_context = "\n".join([f"{m['role']}: {m['message']}" for m in history])

    # Optional lightweight web context about the plant (best-effort, no keys)
    web_summary = None
    web_sources = []
    try:
        if isinstance(plant, dict):
            qname = (plant.get('name') or plant.get('scientific_name') or '').strip()
        else:
            qname = ''
        if qname:
            web_info = plant_ai_web_enrich_fields(qname)
            updates = web_info.get('field_updates') or {}
            web_summary = (updates.get('description') or web_info.get('message') or '').strip() or None
            web_sources = list(web_info.get('sources') or [])
    except Exception:
        web_summary = None
        web_sources = []

    sources_text = (", ".join(web_sources[:3])) if web_sources else ''

    prompt = (
        "You are a helpful gardening assistant for a specific plant's care schedule. "
        "Use the provided database context (SCHEDULE_JSON, PLANT_JSON, ITEM_JSON) and also the WEB_CONTEXT below. "
        "Prefer database facts if there is any conflict. Keep answers concise and practical.\n\n"
        f"PLANT_JSON: {plant_json}\nITEM_JSON: {item_json}\n\nSCHEDULE_JSON: {schedule_json}\n\n"
        f"WEB_CONTEXT: {web_summary or 'None'}\nSOURCES: {sources_text}\n\n"
        f"Conversation so far:\n{chat_context}\n\n"
        f"User: {user_msg}\nAssistant:"
    )

    try:
        model = os.getenv('GEMINI_MODEL') or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        payload = {'contents': [{'parts': [{'text': prompt}]}]}
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        result = resp.json()
        def find_first_text(obj):
            if isinstance(obj, str): return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    r = find_first_text(v)
                    if r: return r
            if isinstance(obj, list):
                for it in obj:
                    r = find_first_text(it)
                    if r: return r
            return None
        ai_text = find_first_text(result) or ''
    except Exception as e:
        print(f"Gemini chat error: {e}")
        ai_text = "Sorry, I couldn't generate a response right now."

    conn, cur = get_db_cursor()
    try:
        cur.execute('INSERT INTO schedule_chats (schedule_id, user_id, role, message) VALUES (%s, %s, %s, %s)', (schedule_id, session.get('user_id'), 'assistant', ai_text))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error saving assistant chat: {e}")
    finally:
        close_db(conn, cur)

    if web_sources:
        try:
            cite = "\nSources: " + ", ".join(web_sources[:3])
            ai_text = (ai_text or '').strip()
            if cite.strip() not in ai_text:
                ai_text = (ai_text + cite).strip()
        except Exception:
            pass
    return jsonify({'assistant': ai_text})

@api_bp.route('/api/schedule/<int:schedule_id>/chat/upload', methods=['POST'])
@login_required
def schedule_chat_upload(schedule_id):
    from backend.models import Schedule
    from database.connection import get_db_cursor, close_db
    import os, time, base64, mimetypes, json, requests
    sched = Schedule.get_by_id(schedule_id)
    if not sched or sched.user_id != session.get('user_id'):
        return jsonify({'error': 'Not authorized'}), 403
    if 'image' not in request.files:
        return jsonify({'error': 'No image provided'}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    allowed = {'png','jpg','jpeg','gif','webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'jpg'
    if ext not in allowed:
        return jsonify({'error': 'Unsupported file type'}), 400
    upload_dir = os.path.join('frontend', 'static', 'uploads', f'schedule_{schedule_id}')
    os.makedirs(upload_dir, exist_ok=True)
    fname = f"{int(time.time())}_{session.get('user_id')}.{ext}"
    path = os.path.join(upload_dir, fname)
    file.save(path)
    rel_path = os.path.join('uploads', f'schedule_{schedule_id}', fname)
    image_url = url_for('static', filename=rel_path)

    # Save user image message
    conn, cur = get_db_cursor()
    try:
        cur.execute('INSERT INTO schedule_chats (schedule_id, user_id, role, message, image_url) VALUES (%s, %s, %s, %s, %s)', (schedule_id, session.get('user_id'), 'user', None, image_url))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error saving image message: {e}")
    finally:
        close_db(conn, cur)

    # If AI not configured, return without analysis
    gemini_key = _get_env('GEMINI_API_KEY')
    if not gemini_key:
        return jsonify({'image_url': image_url, 'assistant': 'AI not configured. Set GEMINI_API_KEY to enable image analysis.'})

    # Build multimodal request with inline image data
    mime = mimetypes.guess_type(path)[0] or 'image/jpeg'
    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode('utf-8')

    # Context: plant, item, schedule
    plant = None
    item = None
    try:
        from backend.models import User as UserModel
        items = UserModel.get_garden(session.get('user_id'))
        item = next((i for i in items if i['garden_id'] == sched.garden_id), None)
        plant = item.get('plant') if item else None
    except Exception:
        plant = None

    schedule_json = sched.schedule_json or '[]'
    plant_json = json.dumps(plant, default=str) if plant else '{}'
    item_json = json.dumps(item, default=str) if item else '{}'

    guidance = (
        "You are an assistant analyzing a user-uploaded image for a specific plant's schedule. "
        "First, decide if the image depicts a plant. If likely NOT a plant, politely say it doesn't appear to be a plant and ask to upload the plant photo; still provide a brief description of the image. "
        "If it IS a plant, identify probable plant characteristics/species (if confident) and relate advice to the PLANT_JSON, ITEM_JSON, and SCHEDULE_JSON. "
        "Be concise, safe, and avoid hallucinations beyond what's visible."
    )

    prompt = f"PLANT_JSON: {plant_json}\nITEM_JSON: {item_json}\nSCHEDULE_JSON: {schedule_json}\n\nAnalyze this image."  # context before image

    try:
        model = os.getenv('GEMINI_MODEL') or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        payload = {
            'contents': [
                {
                    'parts': [
                        {'text': guidance},
                        {'text': prompt},
                        {'inline_data': {'mime_type': mime, 'data': b64}}
                    ]
                }
            ]
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        result = resp.json()
        # extract first text
        def find_first_text(obj):
            if isinstance(obj, str): return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    r = find_first_text(v)
                    if r: return r
            if isinstance(obj, list):
                for it in obj:
                    r = find_first_text(it)
                    if r: return r
            return None
        ai_text = find_first_text(result) or ''
    except Exception as e:
        print(f"Gemini vision error: {e}")
        ai_text = "I couldn't analyze the image right now. Please try again."

    # Persist assistant reply
    conn, cur = get_db_cursor()
    try:
        cur.execute('INSERT INTO schedule_chats (schedule_id, user_id, role, message) VALUES (%s, %s, %s, %s)', (schedule_id, session.get('user_id'), 'assistant', ai_text))
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"Error saving assistant vision chat: {e}")
    finally:
        close_db(conn, cur)

    return jsonify({'image_url': image_url, 'assistant': ai_text})

# Create schedule using OpenAI
@api_bp.route('/garden/schedule/create/<int:garden_id>', methods=['POST'])
@login_required
def garden_schedule_create(garden_id):
    if session.get('is_admin'):
        flash('Admins cannot create schedules')
        return redirect(url_for('api.admin_dashboard'))
    from backend.models import User as UserModel, Schedule
    user_id = session.get('user_id')
    items = UserModel.get_garden(user_id)
    item = next((i for i in items if i['garden_id'] == garden_id), None)
    if not item:
        flash('Garden item not found')
        return redirect(url_for('api.my_garden'))

    # Prepare prompt for AI using plant and user item info
    plant = item['plant']
    duration_total = plant.get('duration_days') or 30
    duration = 60 if int(duration_total) > 60 else int(duration_total)
    # Read selected plant stage from form (optional)
    stage = (request.form.get('stage') or '').strip().lower()
    allowed_stages = {'seed','seedling','vegetative','flowering','fruiting','mature'}
    stage = stage if stage in allowed_stages else 'seed'
    # Include full plant and user-garden item data (JSON) in the prompt so Gemini has all context
    try:
        plant_json = json.dumps(plant, default=str)
    except Exception:
        plant_json = '{}'
    try:
        item_json = json.dumps(item, default=str)
    except Exception:
        item_json = '{}'

    prompt = (
        f"You are a helpful assistant that creates detailed, practical, day-by-day care schedules for plants. "
        f"Important constraints: Use ONLY the plant data (PLANT_JSON) and the user's garden item data (ITEM_JSON) provided below. Do NOT use any outside knowledge, web searches, or assumptions about plant varieties beyond what is in the JSON. If a field is missing, assume safe, minimal care actions. Do NOT include any explanations, guidance, or metadata — return ONLY the JSON array output described below.\n\n"
        f"User-selected current plant stage: {stage}.\n"
        f"Stage requirements: If stage is 'seed', Day 1 must include a task that clearly indicates 'Seeding' and appropriate initial watering. If 'seedling', start with seedling/transplant care. If 'vegetative', focus on growth maintenance. If 'flowering' or 'fruiting', include tasks relevant to those stages (e.g., support, pruning, harvesting readiness checks). Avoid tasks that are inappropriate for the selected stage.\n\n"
        f"Output format (must be followed exactly): Return a JSON array with {duration} objects. Each object must be: {{\"day\": <number starting at 1>, \"tasks\": [<string>, ...]}}. Days must be sequential starting at 1 and there must be exactly {duration} entries (a 60-day block or less if total duration is shorter). Tasks should be concise action items (e.g., \"water 200ml\", \"check soil moisture\", \"fertilize once\"). Do not include any fields other than 'day' and 'tasks'.\n\n"
        f"Context (use only these):\nPLANT_JSON: {plant_json}\n\nITEM_JSON: {item_json}\n\n"
        f"Tailor tasks to the plant and item fields (for example: watering_interval_days, duration_days, type, quantity, planted_on) and the selected stage. Do not reference other plants or external sources.\n\n"
        f"Begin output now — ONLY the JSON array and nothing else."
    )

    import os, requests, json, re
    gemini_key = _get_env('GEMINI_API_KEY')

    if not gemini_key:
        error_msg = 'GEMINI_API_KEY is required. Set the GEMINI_API_KEY environment variable to use Gemini.'
        return render_template('schedule_creator.html', plant=plant, item=item, error=error_msg)

    ai_text = None
    try:
        # Require Gemini only — do not fallback to OpenAI per user request
        if not gemini_key:
            error_msg = 'GEMINI_API_KEY environment variable is required to generate schedules using Gemini.'
            return render_template('schedule_creator.html', plant=plant, item=item, error=error_msg)

        # Use modern Gemini generateContent endpoint and pass API key in X-goog-api-key header
        model = os.getenv('GEMINI_MODEL') or 'gemini-2.0-flash'
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
        payload = {
            'contents': [
                {
                    'parts': [
                        {'text': prompt}
                    ]
                }
            ]
        }

        # Perform request with retries for transient errors
        import time
        resp = None
        last_exception = None
        for attempt in range(1, 4):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                resp.raise_for_status()
                break
            except requests.HTTPError as e:
                status = getattr(e.response, 'status_code', None)
                # Do not retry on client errors like 401/403/404 — return helpful message
                if status in (400, 401, 403, 404):
                    body = ''
                    try:
                        body = e.response.text
                    except Exception:
                        body = ''
                    raise Exception(f'Gemini API returned {status}: {body}')
                last_exception = e
                # Exponential backoff for transient errors
                if attempt < 3:
                    time.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise
            except Exception as e:
                last_exception = e
                if attempt < 3:
                    time.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise
        if resp is None:
            raise Exception(f'Failed to call Gemini API: {last_exception}')

        result = resp.json()
        # Robust extraction for different Gemini response shapes
        ai_text = None
        try:
            # Newer responses include 'candidates' with content blocks
            if isinstance(result, dict):
                if 'candidates' in result and len(result['candidates']) > 0:
                    candidate = result['candidates'][0]
                    # candidate.content may be list of dicts with type 'output_text' and 'text'
                    content = candidate.get('content') or candidate.get('outputs') or candidate.get('result')
                    if isinstance(content, list):
                        parts = []
                        for c in content:
                            if isinstance(c, dict):
                                text = c.get('text') or c.get('content') or c.get('output')
                                if text:
                                    parts.append(str(text))
                                else:
                                    # nested content
                                    for v in c.values():
                                        if isinstance(v, str):
                                            parts.append(v)
                        ai_text = '\n'.join(parts)
                    else:
                        ai_text = str(content)
                # Some responses use 'results' -> each has 'content' list
                elif 'results' in result and isinstance(result['results'], list) and len(result['results'])>0:
                    parts = []
                    for r in result['results']:
                        if isinstance(r, dict):
                            content = r.get('content')
                            if isinstance(content, list):
                                for c in content:
                                    if isinstance(c, dict):
                                        t = c.get('text') or c.get('output')
                                        if t: parts.append(t)
                    ai_text = '\n'.join(parts)
                else:
                    # fallback to any textual field
                    # try to find first string in the JSON
                    def find_first_text(obj):
                        if isinstance(obj, str):
                            return obj
                        if isinstance(obj, dict):
                            for k,v in obj.items():
                                res = find_first_text(v)
                                if res: return res
                        if isinstance(obj, list):
                            for item in obj:
                                res = find_first_text(item)
                                if res: return res
                        return None
                    ai_text = find_first_text(result) or json.dumps(result)
        except Exception:
            ai_text = json.dumps(result)

        # Helper to find first string in nested JSON
        def find_first_text(obj):
            if isinstance(obj, str):
                return obj
            if isinstance(obj, dict):
                for k, v in obj.items():
                    res = find_first_text(v)
                    if res:
                        return res
            if isinstance(obj, list):
                for item in obj:
                    res = find_first_text(item)
                    if res:
                        return res
            return None

        # Try to extract JSON array from ai_text and ensure it has exactly the requested duration days.
        def extract_json_array(text):
            if not text:
                return None
            start = text.find('[')
            end = text.rfind(']')
            if start == -1 or end == -1:
                return None
            json_text = text[start:end+1]
            try:
                parsed = json.loads(json_text)
                return parsed
            except Exception:
                return None

        parsed = extract_json_array(ai_text)
        schedule_json = None
        # If parsed and correct length, accept. Otherwise, attempt up to 2 corrective retries with explicit prompt asking for exact days.
        attempts = 0
        max_attempts = 2
        current_text = ai_text
        while attempts <= max_attempts:
            parsed = extract_json_array(current_text)
            if isinstance(parsed, list) and len(parsed) == int(duration):
                schedule_json = json.dumps(parsed)
                break
            if attempts == max_attempts:
                # final fallback: if parsed exists (even wrong length) accept it, else save raw AI text
                if isinstance(parsed, list):
                    schedule_json = json.dumps(parsed)
                else:
                    schedule_json = json.dumps({'ai_text': ai_text})
                break
            # Build a clarifying prompt that requests exact number of days and strict JSON-only output
            clar_prompt = (
                f"You must return EXACTLY {duration} items. Return ONLY a JSON array with {duration} objects. "
                "Each object should be {\"day\": <number starting at 1>, \"tasks\": [<string>, ...]}. "
                "Do not include any explanation, code fences, or extra text. Use concise actionable tasks appropriate for the plant, the selected stage, and user data provided earlier. "
                f"User-selected stage: {stage}. If stage is 'seed', Day 1 must include a task that clearly indicates 'Seeding' and appropriate initial watering. "
                f"Use ONLY the following context (PLANT_JSON and ITEM_JSON) and nothing else: \nPLANT_JSON: {plant_json}\nITEM_JSON: {item_json}\n"
            )
            # Call Gemini again with the clarification
            payload2 = {'contents': [{'parts': [{'text': clar_prompt}]}]}
            try:
                resp2 = requests.post(url, headers=headers, json=payload2, timeout=120)
                resp2.raise_for_status()
                res2 = resp2.json()
                new_text = find_first_text(res2) or json.dumps(res2)
                current_text = new_text
            except Exception as e:
                # If retry fails, break and fallback
                print(f"Retry {attempts+1} call to Gemini failed: {e}")
                if isinstance(parsed, list):
                    schedule_json = json.dumps(parsed)
                else:
                    schedule_json = json.dumps({'ai_text': ai_text, 'retry_error': str(e)})
                break
            attempts += 1

        schedule = Schedule.create(garden_id=garden_id, user_id=user_id, schedule_json=schedule_json)
        if schedule:
            # Persist individual tasks for checklist
            try:
                parsed_schedule = json.loads(schedule.schedule_json) if schedule.schedule_json else []
            except Exception:
                parsed_schedule = []
            try:
                from backend.models import ScheduleTask
                ScheduleTask.create_many(schedule.id, parsed_schedule)
            except Exception as e:
                print(f"Warning: failed to persist schedule tasks: {e}")

            # If called inline from schedule_creator page, render the creator with checkboxes
            inline = request.form.get('inline') or request.args.get('inline')
            schedule_data = parsed_schedule

            if inline == '1':
                plant_context = item.get('plant') if isinstance(item, dict) else None
                return render_template('schedule_creator.html', plant=plant_context, item=item, schedule=schedule, data=schedule_data)

            flash('Schedule created successfully')
            return redirect(url_for('api.garden_schedule_view', schedule_id=schedule.id))
        else:
            flash('Failed to save schedule')
            return redirect(url_for('api.my_garden'))
    except Exception as e:
        print(f"Error generating schedule via AI: {e}")
        # Return to creator page with error message so the client receives a valid response
        try:
            return render_template('schedule_creator.html', plant=plant, item=item, error=str(e))
        except Exception:
            # As a last resort, return a generic error
            return render_template('schedule_creator.html', plant=None, item=None, error='Failed to generate schedule')


# API: Toggle a schedule task completed state
@api_bp.route('/api/schedule/<int:schedule_id>/task/toggle', methods=['POST'])
@login_required
def api_schedule_task_toggle(schedule_id):
    from backend.models import ScheduleTask
    try:
        data = request.get_json(silent=True) or {}
        day = int(data.get('day'))
        task_index = int(data.get('task_index'))
        completed = bool(data.get('completed'))
        res = ScheduleTask.toggle(session.get('user_id'), schedule_id, day, task_index, completed)
        # If res is a tuple (dict, status), handle it
        if isinstance(res, tuple) and len(res) == 2:
            return jsonify(res[0]), res[1]
        return jsonify(res)
    except Exception as e:
        print(f"Schedule task toggle error: {e}")
        return jsonify({'error': 'Failed to toggle task'}), 500


# API: Save schedule state (tasks + notes) back into schedule_json
@api_bp.route('/api/schedule/<int:schedule_id>/save_state', methods=['POST'])
@login_required
def api_schedule_save_state(schedule_id):
    from backend.models import Schedule
    from database.connection import get_db_cursor, close_db
    try:
        sched = Schedule.get_by_id(schedule_id)
        if not sched or sched.user_id != session.get('user_id'):
            return jsonify({'error': 'Not authorized'}), 403
        data = request.get_json(silent=True) or {}
        state = data.get('state')
        if state is None:
            return jsonify({'error': 'state required'}), 400
        import json as _json
        conn, cur = get_db_cursor()
        try:
            cur.execute('UPDATE schedules SET schedule_json = %s WHERE id = %s', (_json.dumps(state), schedule_id))
            conn.commit()
        finally:
            close_db(conn, cur)
        return jsonify({'message': 'Schedule state saved'})
    except Exception as e:
        print(f"Error saving schedule state: {e}")
        return jsonify({'error': 'Failed to save state'}), 500


        error_msg = f'Failed to generate schedule: {e}'
        return render_template('schedule_creator.html', plant=plant, item=item, error=error_msg)

# Schedule creator page (GET) — shows plant details and a form to generate schedule
@api_bp.route('/garden/schedule/new/<int:garden_id>', methods=['GET'])
@login_required
def garden_schedule_generate(garden_id):
    from backend.models import User as UserModel
    user_id = session.get('user_id')

    if session.get('is_admin'):
        flash('Admins cannot create schedules')
        return redirect(url_for('api.admin_dashboard'))

    items = UserModel.get_garden(user_id)
    item = next((i for i in items if i['garden_id'] == garden_id), None)
    if not item:
        flash('Garden item not found')
        return redirect(url_for('api.my_garden'))

    plant = item.get('plant')
    # If this garden item already has a schedule, load and pass it so the creator shows the saved schedule on refresh
    schedule = None
    data = None
    try:
        sched_id = item.get('schedule_id')
        if sched_id:
            from backend.models import Schedule, ScheduleTask
            schedule = Schedule.get_by_id(sched_id)
            if schedule:
                import json
                try:
                    data = json.loads(schedule.schedule_json)
                except Exception:
                    data = {'raw': schedule.schedule_json}
    except Exception as _:
        # ignore; we'll render without schedule
        schedule = None
        data = None

    return render_template('schedule_creator.html', plant=plant, item=item, schedule=schedule, data=data)

# View a schedule
@api_bp.route('/garden/schedule/<int:schedule_id>')
@login_required
def garden_schedule_view(schedule_id):
    from backend.models import Schedule, User as UserModel
    schedule = Schedule.get_by_id(schedule_id)
    if not schedule:
        flash('Schedule not found')
        return redirect(url_for('api.my_garden'))
    # ensure owner
    if schedule.user_id != session.get('user_id'):
        flash('Not authorized')
        return redirect(url_for('api.my_garden'))
    import json
    try:
        data = json.loads(schedule.schedule_json)
    except Exception:
        data = {'raw': schedule.schedule_json}

    # Try to locate the corresponding garden item to include plant details
    plant = None
    item = None
    tasks_map = {}
    try:
        from backend.models import User as UserModel, ScheduleTask
        items = UserModel.get_garden(session.get('user_id'))
        item = next((i for i in items if i['garden_id'] == schedule.garden_id), None)
        if item:
            plant = item.get('plant')
        # fetch persisted tasks
        rows = ScheduleTask.get_for_schedule(schedule.id)
        for r in rows:
            day = r.get('day')
            if day not in tasks_map:
                tasks_map[day] = []
            tasks_map[day].append({
                'task_index': r.get('task_index'),
                'task_text': r.get('task_text'),
                'completed': bool(r.get('completed'))
            })
    except Exception as e:
        print(f"Warning: could not fetch schedule tasks: {e}")

    return render_template('garden_schedule_view.html', schedule=schedule, data=data, plant=plant, item=item, tasks_map=tasks_map)

# Extend schedule by next 60-day block (or remaining)
@api_bp.route('/garden/schedule/extend/<int:schedule_id>', methods=['POST'])
@login_required
def garden_schedule_extend(schedule_id):
    from backend.models import Schedule, User as UserModel
    import json
    sched = Schedule.get_by_id(schedule_id)
    if not sched:
        flash('Schedule not found')
        return redirect(url_for('api.my_garden'))
    if sched.user_id != session.get('user_id'):
        flash('Not authorized')
        return redirect(url_for('api.my_garden'))

    # Load current schedule JSON
    try:
        current = json.loads(sched.schedule_json) if sched.schedule_json else []
    except Exception:
        current = []

    # Fetch plant/item context
    items = UserModel.get_garden(session.get('user_id'))
    item = next((i for i in items if i['garden_id'] == sched.garden_id), None)
    if not item:
        flash('Garden item not found')
        return redirect(url_for('api.my_garden'))
    plant = item.get('plant') or {}
    duration_total = plant.get('duration_days') or 30

    # Determine next block
    start_day = (len(current) or 0) + 1
    remaining = max(0, int(duration_total) - (start_day - 1))
    if remaining <= 0:
        flash('Schedule already covers full duration')
        return redirect(url_for('api.garden_schedule_view', schedule_id=schedule_id))
    block = 60 if remaining > 60 else remaining

    # Stage hint: default to vegetative for extensions
    stage = (request.form.get('stage') or '').strip().lower() or 'vegetative'

    # Build prompt for next block with day numbers starting at start_day
    try:
        plant_json = json.dumps(plant, default=str)
    except Exception:
        plant_json = '{}'
    try:
        item_json = json.dumps(item, default=str)
    except Exception:
        item_json = '{}'

    prompt = (
        f"You are a helpful assistant that extends a day-by-day care schedule. "
        f"Generate ONLY the next {block} days starting at day {start_day}. "
        f"Important: Use ONLY PLANT_JSON and ITEM_JSON provided. Keep tasks consistent with prior care. Stage hint: {stage}.\n\n"
        f"Output format: Return a JSON array with {block} objects. Each object must be {{\"day\": <number starting at {start_day}>, \"tasks\": [<string>, ...]}}. Days must be sequential starting at {start_day} and there must be exactly {block} entries.\n\n"
        f"PLANT_JSON: {plant_json}\n\nITEM_JSON: {item_json}\n\n"
        f"Begin output now — ONLY the JSON array."
    )

    gemini_key = _get_env('GEMINI_API_KEY')
    if not gemini_key:
        flash('GEMINI_API_KEY required to extend schedule')
        return redirect(url_for('api.garden_schedule_view', schedule_id=schedule_id))

    import requests
    model = os.getenv('GEMINI_MODEL') or 'gemini-2.0-flash'
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
    payload = {'contents': [{'parts': [{'text': prompt}]}]}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        res = resp.json()
        def find_first_text(obj):
            if isinstance(obj, str): return obj
            if isinstance(obj, dict):
                for v in obj.values():
                    x = find_first_text(v)
                    if x: return x
            if isinstance(obj, list):
                for it in obj:
                    x = find_first_text(it)
                    if x: return x
            return None
        text = find_first_text(res) or ''
        # extract JSON array
        def extract(text):
            s = text.find('['); e = text.rfind(']')
            if s == -1 or e == -1: return None
            import json as _json
            try:
                return _json.loads(text[s:e+1])
            except Exception:
                return None
        new_part = extract(text) or []
        if not isinstance(new_part, list) or len(new_part) != block:
            flash('AI returned invalid schedule block')
            return redirect(url_for('api.garden_schedule_view', schedule_id=schedule_id))

        # Append and persist
        merged = list(current) + list(new_part)
        merged_json = json.dumps(merged)
        from database.connection import get_db_cursor, close_db
        conn, cur = get_db_cursor()
        try:
            cur.execute('UPDATE schedules SET schedule_json = %s WHERE id = %s RETURNING id', (merged_json, schedule_id))
            ok = cur.fetchone()
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error updating schedule block: {e}")
            flash('Failed to extend schedule')
            return redirect(url_for('api.garden_schedule_view', schedule_id=schedule_id))
        finally:
            close_db(conn, cur)

        # Persist tasks for the new days
        try:
            from backend.models import ScheduleTask
            ScheduleTask.create_many(schedule_id, new_part)
        except Exception as e:
            print(f"Warning: failed to persist extended tasks: {e}")

        flash('Next 60-day block added')
        return redirect(url_for('api.garden_schedule_view', schedule_id=schedule_id))
    except Exception as e:
        print(f"Error extending schedule: {e}")
        flash('Failed to extend schedule')
        return redirect(url_for('api.garden_schedule_view', schedule_id=schedule_id))

@api_bp.route('/admin/users/add', methods=['POST'])
@admin_required
def admin_add_user():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    if not all([username, email, password]):
        flash('All fields are required to add a user')
        return redirect(url_for('api.admin_dashboard'))

    if len(password) < 8:
        flash('Password must be at least 8 characters')
        return redirect(url_for('api.admin_dashboard'))

    role = request.form.get('role', 'user')
    is_pro = True if (request.form.get('is_pro') or '').lower() in ('1','true','on','yes') else False
    try:
        if User.user_exists(username, email):
            flash('Username or email already exists')
            return redirect(url_for('api.admin_dashboard'))
        User.create(username, email, password, role=role, is_pro=is_pro)
        flash('User added successfully')
    except Exception as e:
        print(f"Error adding user: {e}")
        flash('Failed to add user')
    return redirect(url_for('api.admin_dashboard'))

@api_bp.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def admin_delete_user(user_id):
    try:
        if User.delete_by_id(user_id):
            flash('User deleted successfully')
        else:
            flash('User not found or could not be deleted')
    except Exception as e:
        print(f"Error deleting user: {e}")
        flash('Failed to delete user')
    return redirect(url_for('api.admin_dashboard'))

# Market sub-admin dashboard
@api_bp.route('/subadmin/market')
@admin_or_market_required

def subadmin_market():
    # Market sub-admins and admins can access this simplified panel
    products = Product.get_all()
    return render_template('subadmin_market.html', products=products)

# Plant admin routes
@api_bp.route('/admin/plants')
@admin_or_subadmin_required
def admin_plants():
    plants = Plant.get_all()
    return render_template('admin_plants.html', plants=plants)


@api_bp.route('/api/admin/plants/ai/suggest', methods=['POST'])
@admin_or_subadmin_required
def admin_ai_plant_suggest():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    photo_url = (data.get('photo_url') or '').strip()

    if not name:
        return jsonify({'error': 'Plant name is required'}), 400

    plants = Plant.get_all()
    dataset = build_plant_ai_dataset(plants)
    gemini_key = _get_env('GEMINI_API_KEY')
    model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'

    if not gemini_key:
        duplicate_record = plant_ai_duplicate_by_name(name, dataset) or plant_ai_duplicate_by_scientific(
            data.get('scientific_name'), dataset
        )
        if duplicate_record:
            return jsonify({
                'message': (
                    f"Plant '{duplicate_record.name}' already exists (ID {duplicate_record.id}). "
                    'Here are its saved details for reference.'
                ),
                'fields': plant_ai_record_fields(duplicate_record, fallback_photo=photo_url or duplicate_record.photo_url),
                'duplicate': True,
                'similar_matches': plant_ai_similar_matches(name, dataset, exclude_id=duplicate_record.id),
            })
        fallback = {
            'message': 'Configure GEMINI_API_KEY to enable AI suggestions. Showing basic draft only.',
            'fields': {
                'name': name,
                'photo_url': photo_url,
            },
            'duplicate': False,
            'similar_matches': plant_ai_similar_matches(name, dataset),
        }
        return jsonify(fallback), 503

    try:
        # Always attempt a lightweight web enrichment to propose safe defaults first
        web_enrich = plant_ai_web_enrich_fields(name)
        suggestion = plant_ai_generate_suggestion(
            name,
            photo_url,
            dataset,
            api_key=gemini_key,
            model=model,
        )
        # Attach web findings for the UI to preview and accept before applying
        suggestion['web_details'] = web_enrich
        return jsonify(suggestion)
    except PlantAIHelperError as exc:
        status_code = 503 if 'key' in str(exc).lower() else 500
        return jsonify({'error': str(exc)}), status_code
    except Exception:
        return jsonify({'error': 'Failed to generate plant suggestion'}), 500


@api_bp.route('/api/admin/plants/ai/chat', methods=['POST'])
@admin_or_subadmin_required
def admin_ai_plant_chat():
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({'error': 'Message is required'}), 400

    conversation = data.get('conversation') or []
    fields = data.get('fields') or {}

    plants = Plant.get_all()
    dataset = build_plant_ai_dataset(plants)
    gemini_key = _get_env('GEMINI_API_KEY')
    model = _get_env('GEMINI_MODEL') or 'gemini-2.0-flash'

    if not gemini_key:
        duplicate_record = plant_ai_duplicate_by_name(fields.get('name'), dataset) or plant_ai_duplicate_by_scientific(
            fields.get('scientific_name'), dataset
        )
        similar = plant_ai_similar_matches(fields.get('name') or message, dataset)
        if duplicate_record:
            record_fields = plant_ai_record_fields(duplicate_record)
            response_payload = {
                'message': (
                    f"Plant '{duplicate_record.name}' already exists (ID {duplicate_record.id}). "
                    'Configure GEMINI_API_KEY to enable live AI editing.'
                ),
                'field_updates': record_fields,
                'duplicate': True,
                'similar_matches': similar,
                'merged_fields': record_fields,
            }
        else:
            response_payload = {
                'message': 'Configure GEMINI_API_KEY to enable live AI editing.',
                'field_updates': {},
                'duplicate': False,
                'similar_matches': similar,
                'merged_fields': fields,
            }
        return jsonify(response_payload), 503

    try:
        response_payload = plant_ai_chat_response(
            message,
            conversation,
            fields,
            dataset,
            api_key=gemini_key,
            model=model,
        )
        # If the admin asked to autofill or search, propose web-based updates too (never auto-apply)
        msg_lc = (message or '').lower()
        if any(k in msg_lc for k in ['autofill', 'auto fill', 'search', 'from web', 'web', 'wikipedia']):
            name_for_lookup = (fields.get('name') or '').strip() or message
            web_enrich = plant_ai_web_enrich_fields(name_for_lookup)
            if web_enrich and isinstance(web_enrich.get('field_updates'), dict):
                response_payload.setdefault('proposed_updates', {}).update(web_enrich['field_updates'])
                # Add a short note into the assistant message so the UI can display context
                note = web_enrich.get('message') or ''
                if note:
                    response_payload['message'] = (response_payload.get('message') or '').strip()
                    if response_payload['message']:
                        response_payload['message'] += ' '
                    response_payload['message'] += note
                if web_enrich.get('sources'):
                    response_payload['sources'] = web_enrich['sources']

        return jsonify(response_payload)
    except PlantAIHelperError as exc:
        status_code = 503 if 'key' in str(exc).lower() else 500
        return jsonify({'error': str(exc)}), status_code
    except Exception:
        return jsonify({'error': 'Failed to process AI chat message'}), 500


@api_bp.route('/subadmin')
@admin_or_subadmin_required
def subadmin_dashboard():
    # Only sub-admin users should land here; admins are redirected to full admin panel
    if session.get('is_admin') and not session.get('is_sub_admin'):
        return redirect(url_for('api.admin_dashboard'))
    plants = Plant.get_all()
    return render_template('subadmin.html', plants=plants)

@api_bp.route('/admin/plants/add', methods=['POST'])
@admin_or_subadmin_required
def admin_add_plant():
    name = request.form.get('name', '').strip()
    scientific_name = request.form.get('scientific_name', '').strip()
    duration_days = request.form.get('duration_days', '').strip()
    plant_type = request.form.get('type', '').strip()
    photo_url = request.form.get('photo_url', '').strip()
    description = request.form.get('description', '').strip()
    sunlight = (request.form.get('sunlight') or '').strip() or None
    spacing_cm = request.form.get('spacing_cm') or None
    watering_needs = (request.form.get('watering_needs') or '').strip() or None
    model_url = (request.form.get('model_url') or '').strip() or None
    growth_height_cm = request.form.get('growth_height_cm') or None
    growth_width_cm = request.form.get('growth_width_cm') or None

    if not all([name, scientific_name, duration_days, plant_type, photo_url, description]):
        flash('All plant fields are required')
        return redirect(url_for('api.admin_plants'))

    try:
        duration = int(duration_days)
    except ValueError:
        flash('Duration must be a valid integer (days)')
        return redirect(url_for('api.admin_plants'))

    try:
        spacing_val = int(spacing_cm) if spacing_cm else None
        gh = int(growth_height_cm) if growth_height_cm else None
        gw = int(growth_width_cm) if growth_width_cm else None
    except Exception:
        flash('Spacing/Size must be valid integers')
        return redirect(url_for('api.admin_plants'))

    try:
        Plant.create(name, scientific_name, duration, plant_type, photo_url, description, sunlight=sunlight or None, spacing_cm=spacing_val, watering_needs=watering_needs or None, model_url=model_url or None, growth_height_cm=gh, growth_width_cm=gw)
        flash('Plant added successfully')
    except Exception as e:
        print(f"Error adding plant: {e}")
        flash('Failed to add plant')
    return redirect(url_for('api.admin_plants'))

@api_bp.route('/admin/plants/edit/<int:plant_id>', methods=['GET', 'POST'])
@admin_or_subadmin_required
def admin_edit_plant(plant_id):
    plant = Plant.get_by_id(plant_id)
    if not plant:
        flash('Plant not found')
        return redirect(url_for('api.admin_plants'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        scientific_name = request.form.get('scientific_name', '').strip()
        duration_days = request.form.get('duration_days', '').strip()
        plant_type = request.form.get('type', '').strip()
        photo_url = request.form.get('photo_url', '').strip()
        description = request.form.get('description', '').strip()
        sunlight = (request.form.get('sunlight') or '').strip() or None
        spacing_cm = request.form.get('spacing_cm') or None
        watering_needs = (request.form.get('watering_needs') or '').strip() or None
        model_url = (request.form.get('model_url') or '').strip() or None
        growth_height_cm = request.form.get('growth_height_cm') or None
        growth_width_cm = request.form.get('growth_width_cm') or None

        if not all([name, scientific_name, duration_days, plant_type, photo_url, description]):
            flash('All plant fields are required')
            return redirect(url_for('api.admin_edit_plant', plant_id=plant_id))

        try:
            duration = int(duration_days)
        except ValueError:
            flash('Duration must be a valid integer (days)')
            return redirect(url_for('api.admin_edit_plant', plant_id=plant_id))

        try:
            spacing_val = int(spacing_cm) if spacing_cm else None
            gh = int(growth_height_cm) if growth_height_cm else None
            gw = int(growth_width_cm) if growth_width_cm else None
        except Exception:
            flash('Spacing/Size must be valid integers')
            return redirect(url_for('api.admin_edit_plant', plant_id=plant_id))

        try:
            if Plant.update(plant_id, name, scientific_name, duration, plant_type, photo_url, description, sunlight=sunlight or None, spacing_cm=spacing_val, watering_needs=watering_needs or None, model_url=model_url or None, growth_height_cm=gh, growth_width_cm=gw):
                flash('Plant updated successfully')
            else:
                flash('Failed to update plant')
        except Exception as e:
            print(f"Error updating plant: {e}")
            flash('Failed to update plant')
        return redirect(url_for('api.admin_plants'))

    return render_template('admin_plants_edit.html', plant=plant)

@api_bp.route('/admin/plants/delete/<int:plant_id>', methods=['POST'])
@admin_or_subadmin_required
def admin_delete_plant(plant_id):
    try:
        if Plant.delete_by_id(plant_id):
            flash('Plant deleted successfully')
        else:
            flash('Plant not found or could not be deleted')
    except Exception as e:
        print(f"Error deleting plant: {e}")
        flash('Failed to delete plant')
    return redirect(url_for('api.admin_plants'))

# Plant JSON API
@api_bp.route('/api/plants', methods=['GET'])
@login_required
def api_get_plants():
    plants = Plant.get_all()
    result = []
    for p in plants:
        result.append({
            'id': p.id,
            'name': p.name,
            'scientific_name': p.scientific_name,
            'duration_days': p.duration_days,
            'type': p.type,
            'photo_url': p.photo_url,
            'description': p.description,
            'sunlight': getattr(p, 'sunlight', None),
            'spacing_cm': getattr(p, 'spacing_cm', None),
            'watering_needs': getattr(p, 'watering_needs', None),
            'model_url': getattr(p, 'model_url', None),
            'growth_height_cm': getattr(p, 'growth_height_cm', None),
            'growth_width_cm': getattr(p, 'growth_width_cm', None),
            'created_at': p.created_at,
            'updated_at': p.updated_at
        })
    return jsonify(result)

@api_bp.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'auth-app',
        'version': '1.0.0'
    })

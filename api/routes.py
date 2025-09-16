from flask import Blueprint, render_template, request, redirect, url_for, jsonify, session, flash
from backend.models import User, Plant, Product
from backend.auth import login_required, login_user, logout_user, admin_required, admin_or_subadmin_required, admin_or_market_required

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

@api_bp.route('/')
def index():
    if 'user_id' in session or session.get('is_admin'):
        return redirect(url_for('api.dashboard'))
    return redirect(url_for('api.login'))

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
                # If sub-admins, send to their respective dashboards
                if session.get('is_sub_admin'):
                    return redirect(url_for('api.subadmin_dashboard'))
                if session.get('is_market_admin'):
                    return redirect(url_for('api.subadmin_market'))
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
        
        if len(password) < 6:
            return render_template('register.html', error='Password must be at least 6 characters')
        
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

    return render_template('dashboard.html', username=username, plants=plants, garden=garden, products=products, profile=profile, notifications=notifications)


# AI Assistant (global) page and chat endpoints using Perplexity API
@api_bp.route('/ai')
@login_required
def ai_assistant_page():
    return render_template('ai_assistant.html')

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
        "You are a friendly gardening assistant. Be concise and practical. "
        "If the user has plants, tailor advice to them when relevant."
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

    return jsonify({'assistant': ai_text})

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
            return jsonify(body), code
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
    if session.get('is_admin'):
        flash('Admins cannot add plants to a garden')
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

    try:
        from backend.models import User as UserModel
        added = UserModel.add_to_garden(user_id, plant_id, nickname=nickname or None, planted_on=planted_on, quantity=int(quantity) if quantity else 1, location=location or None, watering_interval_days=int(watering_interval_days) if watering_interval_days else None, notes=notes or None, last_watered=last_watered or None)
        if added:
            flash('Plant added to your garden')
        else:
            flash('Plant was already in your garden or could not be added')
    except Exception as e:
        print(f"Error adding plant to garden: {e}")
        flash('Failed to add plant to garden')
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
    if session.get('is_admin'):
        flash('Admins cannot modify gardens')
        return redirect(url_for('api.admin_dashboard'))
    user_id = session.get('user_id')
    try:
        from backend.models import User as UserModel
        if UserModel.remove_from_garden(user_id, plant_id):
            flash('Plant removed from your garden')
        else:
            flash('Plant not found in your garden')
    except Exception as e:
        print(f"Error removing plant from garden: {e}")
        flash('Failed to remove plant from garden')
    return redirect(url_for('api.dashboard'))

@api_bp.route('/logout')
def logout():
    username = session.get('username', 'Unknown')
    logout_user()
    print(f"✅ User {username} logged out")
    return redirect(url_for('api.login'))

# Admin routes
@api_bp.route('/admin')
@admin_required
def admin_dashboard():
    users = User.get_all()
    return render_template('admin.html', users=users)

# Marketplace admin routes
@api_bp.route('/admin/market')
@admin_or_market_required
def admin_market():
    products = Product.get_all()
    return render_template('admin_market.html', products=products)

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
        return redirect(url_for('api.admin_market'))

    try:
        price_val = float(price)
    except ValueError:
        flash('Price must be a number')
        return redirect(url_for('api.admin_market'))

    try:
        qty_val = int(quantity)
        if qty_val < 0:
            raise ValueError('quantity negative')
    except ValueError:
        flash('Quantity must be a non-negative integer')
        return redirect(url_for('api.admin_market'))

    try:
        Product.create(name, product_type, image_url, buy_url, price_val, qty_val, unit, brand, description)
        flash('Product added successfully')
    except Exception as e:
        print(f"Error adding product: {e}")
        flash('Failed to add product')
    return redirect(url_for('api.admin_market'))

@api_bp.route('/admin/market/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_or_market_required
def admin_edit_product(product_id):
    product = Product.get_by_id(product_id)
    if not product:
        flash('Product not found')
        return redirect(url_for('api.admin_market'))

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
            return redirect(url_for('api.admin_edit_product', product_id=product_id))

        try:
            price_val = float(price)
        except ValueError:
            flash('Price must be a number')
            return redirect(url_for('api.admin_edit_product', product_id=product_id))

        try:
            qty_val = int(quantity)
            if qty_val < 0:
                raise ValueError('quantity negative')
        except ValueError:
            flash('Quantity must be a non-negative integer')
            return redirect(url_for('api.admin_edit_product', product_id=product_id))

        try:
            if Product.update(product_id, name, product_type, image_url, buy_url, price_val, qty_val, unit, brand, description):
                flash('Product updated successfully')
            else:
                flash('Failed to update product')
        except Exception as e:
            print(f"Error updating product: {e}")
            flash('Failed to update product')
        return redirect(url_for('api.admin_market'))

    return render_template('admin_market_edit.html', product=product)

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
    return redirect(url_for('api.admin_market'))

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
    prompt = (
        "You are a helpful gardening assistant for a specific plant's care schedule. "
        "Answer based ONLY on the provided SCHEDULE_JSON, PLANT_JSON, and ITEM_JSON. "
        "If asked for next schedule details, summarize upcoming tasks. "
        "Be practical and concise. If an image is mentioned, acknowledge it but do not guess beyond provided info.\n\n"
        f"PLANT_JSON: {plant_json}\nITEM_JSON: {item_json}\n\nSCHEDULE_JSON: {schedule_json}\n\n"
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
    duration = plant.get('duration_days') or 30
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
        f"Output format (must be followed exactly): Return a JSON array with {duration} objects. Each object must be: {{\"day\": <number starting at 1>, \"tasks\": [<string>, ...]}}. Days must be sequential starting at 1 and there must be exactly {duration} entries. Tasks should be concise action items (e.g., \"water 200ml\", \"check soil moisture\", \"fertilize once\"). Do not include any fields other than 'day' and 'tasks'.\n\n"
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
    return render_template('schedule_creator.html', plant=plant, item=item)

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

@api_bp.route('/admin/users/add', methods=['POST'])
@admin_required
def admin_add_user():
    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    if not all([username, email, password]):
        flash('All fields are required to add a user')
        return redirect(url_for('api.admin_dashboard'))

    if len(password) < 6:
        flash('Password must be at least 6 characters')
        return redirect(url_for('api.admin_dashboard'))

    role = request.form.get('role', 'user')
    try:
        if User.user_exists(username, email):
            flash('Username or email already exists')
            return redirect(url_for('api.admin_dashboard'))
        User.create(username, email, password, role=role)
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

    if not all([name, scientific_name, duration_days, plant_type, photo_url, description]):
        flash('All plant fields are required')
        return redirect(url_for('api.admin_plants'))

    try:
        duration = int(duration_days)
    except ValueError:
        flash('Duration must be a valid integer (days)')
        return redirect(url_for('api.admin_plants'))

    try:
        Plant.create(name, scientific_name, duration, plant_type, photo_url, description)
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

        if not all([name, scientific_name, duration_days, plant_type, photo_url, description]):
            flash('All plant fields are required')
            return redirect(url_for('api.admin_edit_plant', plant_id=plant_id))

        try:
            duration = int(duration_days)
        except ValueError:
            flash('Duration must be a valid integer (days)')
            return redirect(url_for('api.admin_edit_plant', plant_id=plant_id))

        try:
            if Plant.update(plant_id, name, scientific_name, duration, plant_type, photo_url, description):
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

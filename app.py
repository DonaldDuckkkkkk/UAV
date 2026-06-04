import os
import json
import time
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'secure_military_key_shadow'

# Конфігурація додатку
UPLOAD_FOLDER = os.path.join(app.root_path, 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
DB_FILE = os.path.join(app.root_path, 'uav_database.json')

app.config.update({
    'UPLOAD_FOLDER': UPLOAD_FOLDER,
    'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,
    'JSON_AS_ASCII': False,
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'Lax',
    'TEMPLATES_AUTO_RELOAD': False,
})

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ADMIN_CREDENTIALS = {
    'username': 'admin',
    'password': 'password123'
}

DEFAULT_DATABASE = [
    {
        'id': 1,
        'name': 'Зала',
        'type': 'Розвідувально-камікадзе',
        'manufacturer': 'рф',
        'status': '30-40% втрат',
        
        # Основні характеристики
        'wingspan': '2,8 м',
        'max_weight': '7,5 кг',
        'flight_time': 'до 4 годин',
        'max_altitude': '5 000 м',
        'work_altitude': 'не вказана',
        'max_speed': '125 км/год',
        'work_speed': '70-125 км/год',
        'max_payload': '1,5 кг',
        'engine_type': 'не вказаний',
        
        # Камери
        'main_camera': '60x оптичне збільшення',
        'thermal_camera': 'так',
        'thermal_type': 'не вказана',
        
        # Радіус дії
        'realtime_range': '35-50 км (передача в реальному часі)',
        'autonomy_range': '100-120 км',
        
        # Навігація
        'navigation': 'ІНС з корекцією по СРНС, подвійний радіодалекомір, радіомаяки',
        'nav_systems': ['GPS', 'Galileo', 'Beidou', 'ГЛОНАСС'],
        
        # КТР - Управління та телеметрія
        'ktr_frequency': '~860-880, ~902-928 МГц (960-1080+)',
        'ktr_bandwidth': 'зазвичай 1 МГц',
        'ktr_modulation': 'ППРЧ, 2FSK у формі "М"',
        'ktr_details': 'Частотно-маніпульований сигнал з неперервною фазою. Частотний зсув 160кГц. Швидкість маніпуляції 15,238 кбіт/с',
        'ktr_freq_channels': [869.4, 870.7, 914, 915],
        'ktr_channel_868': 'Інколи телеметрія на 868 МГц',
        
        # Редіомаяки
        'radiobeacons': '869-870 та 914-915 МГц',
        
        # Відеоканал
        'video_frequency': '2,1 - 2,4 ГГц',
        'video_bandwidth': '~4 МГц',
        'video_modulation': 'Цифровий, шифрований, COFDM',
        'video_mode': 'TDD режим',
        'video_frame': '56 мс, 16 тайм-слотів по 3 мс',
        
        # Розпізнання об'єктів
        'recognition': {
            '500m': 'пікселю форму об\'єкту',
            '1000m': 'людину у військовому комплекті',
            '2000m': 'людину біля будівель, погано замаскавану техніку',
            '3000m': 'виявлення руху техніки',
            '3000m+': 'озброєння на підставі пуску ракет, артилерійських залпів'
        },
        
        'avatar': 'mock_orlan.jpg',
        'spectrum': 'mock_spectrum.jpg',
        'extra_photos': []
    }
]


def load_db():
    if not os.path.exists(DB_FILE):
        save_db(DEFAULT_DATABASE)
        return list(DEFAULT_DATABASE)

    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return list(DEFAULT_DATABASE)


def save_db(data):
    temp_path = f'{DB_FILE}.tmp'
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    os.replace(temp_path, DB_FILE)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Доступ заборонено. Необхідна авторизація.', 'error')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view


def safe_file_save(file_storage, prefix):
    if not file_storage or file_storage.filename == '':
        return ''

    if not allowed_file(file_storage.filename):
        return ''

    filename = f'{prefix}_{int(time.time())}_{secure_filename(file_storage.filename)}'
    destination = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file_storage.save(destination)
    return filename


def get_uav_by_id(uav_id):
    return next((item for item in load_db() if item['id'] == uav_id), None)


def remove_file(filename):
    if not filename:
        return
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def validate_uav_form(form, files, is_edit=False):
    name = form.get('name', '').strip()
    uav_type = form.get('type', '').strip()
    manufacturer = form.get('manufacturer', '').strip()
    frequency = form.get('frequency', '').strip()
    description = form.get('description', '').strip()
    avatar_file = files.get('avatar')
    spectrum_file = files.get('spectrum')

    errors = []
    if not name:
        errors.append('Поле "Назва" є обов’язковим.')
    if not uav_type:
        errors.append('Поле "Тип" є обов’язковим.')
    if not manufacturer:
        errors.append('Поле "Виробник" є обов’язковим.')
    if not frequency:
        errors.append('Поле "Частота" є обов’язковим.')
    if not description:
        errors.append('Поле "Опис" є обов’язковим.')

    if not is_edit:
        if not avatar_file or avatar_file.filename == '':
            errors.append('Завантажте фото аватара для БПЛА.')
        if not spectrum_file or spectrum_file.filename == '':
            errors.append('Завантажте фото спектру для БПЛА.')

    return {
        'name': name,
        'type': uav_type,
        'manufacturer': manufacturer,
        'frequency': frequency,
        'description': description,
        'status': form.get('status', '').strip(),
        'wingspan': form.get('wingspan', '').strip(),
        'max_weight': form.get('max_weight', '').strip(),
        'flight_time': form.get('flight_time', '').strip(),
        'max_altitude': form.get('max_altitude', '').strip(),
        'work_altitude': form.get('work_altitude', '').strip(),
        'max_speed': form.get('max_speed', '').strip(),
        'work_speed': form.get('work_speed', '').strip(),
        'max_payload': form.get('max_payload', '').strip(),
        'main_camera': form.get('main_camera', '').strip(),
        'thermal_camera': form.get('thermal_camera', '').strip(),
        'thermal_type': form.get('thermal_type', '').strip(),
        'realtime_range': form.get('realtime_range', '').strip(),
        'autonomy_range': form.get('autonomy_range', '').strip(),
        'navigation': form.get('navigation', '').strip(),
        'ktr_frequency': form.get('ktr_frequency', '').strip(),
        'ktr_bandwidth': form.get('ktr_bandwidth', '').strip(),
        'ktr_modulation': form.get('ktr_modulation', '').strip(),
        'ktr_details': form.get('ktr_details', '').strip(),
        'video_frequency': form.get('video_frequency', '').strip(),
        'video_bandwidth': form.get('video_bandwidth', '').strip(),
        'video_modulation': form.get('video_modulation', '').strip(),
        'avatar_file': avatar_file,
        'spectrum_file': spectrum_file,
        'extra_files': files.getlist('extra_photos')
    }, errors


@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/')
def index():
    search_query = request.args.get('search', '').strip().lower()
    uav_database = load_db()

    if search_query:
        filtered_list = [
            uav for uav in uav_database
            if search_query in uav['name'].lower() or search_query in uav['type'].lower()
        ]
    else:
        filtered_list = uav_database

    return render_template('index.html', uav_list=filtered_list, search_query=request.args.get('search', ''))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        if username == ADMIN_CREDENTIALS['username'] and password == ADMIN_CREDENTIALS['password']:
            session['is_admin'] = True
            flash('Авторизацію успішно пройдено.', 'success')
            return redirect(url_for('admin_panel'))

        flash('Невірний логін або пароль.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('is_admin', None)
    flash('Ви вийшли з системи.', 'info')
    return redirect(url_for('index'))


@app.route('/admin')
@admin_required
def admin_panel():
    return render_template('admin_panel.html', uav_list=load_db())


@app.route('/add', methods=['GET', 'POST'])
@admin_required
def add_uav():
    if request.method == 'POST':
        form_data, errors = validate_uav_form(request.form, request.files)
        for error in errors:
            flash(error, 'error')
        if errors:
            return render_template(
                'uav_form.html',
                uav={
                    'name': form_data['name'],
                    'type': form_data['type'],
                    'manufacturer': form_data['manufacturer'],
                    'frequency': form_data['frequency'],
                    'description': form_data['description'],
                    'avatar': '',
                    'spectrum': '',
                    'extra_photos': []
                },
                form_title='Додати новий БПЛА',
                submit_text='Зберегти',
                form_action=url_for('add_uav')
            )

        avatar_name = safe_file_save(form_data['avatar_file'], 'avatar')
        spectrum_name = safe_file_save(form_data['spectrum_file'], 'spectrum')
        extra_photos = []
        for file in form_data['extra_files']:
            item_name = safe_file_save(file, 'extra')
            if item_name:
                extra_photos.append(item_name)

        uav_database = load_db()
        new_id = max([uav['id'] for uav in uav_database], default=0) + 1
        uav_database.append({
            'id': new_id,
            'name': form_data['name'],
            'type': form_data['type'],
            'manufacturer': form_data['manufacturer'],
            'frequency': form_data['frequency'],
            'description': form_data['description'],
            'status': form_data['status'],
            'wingspan': form_data['wingspan'],
            'max_weight': form_data['max_weight'],
            'flight_time': form_data['flight_time'],
            'max_altitude': form_data['max_altitude'],
            'work_altitude': form_data['work_altitude'],
            'max_speed': form_data['max_speed'],
            'work_speed': form_data['work_speed'],
            'max_payload': form_data['max_payload'],
            'main_camera': form_data['main_camera'],
            'thermal_camera': form_data['thermal_camera'],
            'thermal_type': form_data['thermal_type'],
            'realtime_range': form_data['realtime_range'],
            'autonomy_range': form_data['autonomy_range'],
            'navigation': form_data['navigation'],
            'ktr_frequency': form_data['ktr_frequency'],
            'ktr_bandwidth': form_data['ktr_bandwidth'],
            'ktr_modulation': form_data['ktr_modulation'],
            'ktr_details': form_data['ktr_details'],
            'video_frequency': form_data['video_frequency'],
            'video_bandwidth': form_data['video_bandwidth'],
            'video_modulation': form_data['video_modulation'],
            'avatar': avatar_name,
            'spectrum': spectrum_name,
            'extra_photos': extra_photos
        })
        save_db(uav_database)

        flash('Новий БПЛА успішно додано до каталогу.', 'success')
        return redirect(url_for('admin_panel'))

    return render_template('uav_form.html', uav={}, form_title='Додати новий БПЛА', submit_text='Зберегти', form_action=url_for('add_uav'))


@app.route('/edit/<int:uav_id>', methods=['GET', 'POST'])
@admin_required
def edit_uav(uav_id):
    uav = get_uav_by_id(uav_id)
    if uav is None:
        flash('Обраний запис не знайдено.', 'error')
        return redirect(url_for('admin_panel'))

    if request.method == 'POST':
        form_data, errors = validate_uav_form(request.form, request.files, is_edit=True)
        for error in errors:
            flash(error, 'error')
        if errors:
            return render_template(
                'uav_form.html',
                uav={
                    'id': uav['id'],
                    'name': form_data['name'],
                    'type': form_data['type'],
                    'manufacturer': form_data['manufacturer'],
                    'frequency': form_data['frequency'],
                    'description': form_data['description'],
                    'avatar': uav.get('avatar', ''),
                    'spectrum': uav.get('spectrum', ''),
                    'extra_photos': uav.get('extra_photos', [])
                },
                form_title='Редагувати БПЛА',
                submit_text='Оновити',
                form_action=url_for('edit_uav', uav_id=uav_id)
            )

        avatar_name = safe_file_save(form_data['avatar_file'], 'avatar')
        spectrum_name = safe_file_save(form_data['spectrum_file'], 'spectrum')
        extra_photos = list(uav.get('extra_photos', []))
        for file in form_data['extra_files']:
            item_name = safe_file_save(file, 'extra')
            if item_name:
                extra_photos.append(item_name)

        updated_uav = {
            'id': uav['id'],
            'name': form_data['name'],
            'type': form_data['type'],
            'manufacturer': form_data['manufacturer'],
            'frequency': form_data['frequency'],
            'description': form_data['description'],
            'status': form_data['status'] or uav.get('status', ''),
            'wingspan': form_data['wingspan'] or uav.get('wingspan', ''),
            'max_weight': form_data['max_weight'] or uav.get('max_weight', ''),
            'flight_time': form_data['flight_time'] or uav.get('flight_time', ''),
            'max_altitude': form_data['max_altitude'] or uav.get('max_altitude', ''),
            'work_altitude': form_data['work_altitude'] or uav.get('work_altitude', ''),
            'max_speed': form_data['max_speed'] or uav.get('max_speed', ''),
            'work_speed': form_data['work_speed'] or uav.get('work_speed', ''),
            'max_payload': form_data['max_payload'] or uav.get('max_payload', ''),
            'main_camera': form_data['main_camera'] or uav.get('main_camera', ''),
            'thermal_camera': form_data['thermal_camera'] or uav.get('thermal_camera', ''),
            'thermal_type': form_data['thermal_type'] or uav.get('thermal_type', ''),
            'realtime_range': form_data['realtime_range'] or uav.get('realtime_range', ''),
            'autonomy_range': form_data['autonomy_range'] or uav.get('autonomy_range', ''),
            'navigation': form_data['navigation'] or uav.get('navigation', ''),
            'ktr_frequency': form_data['ktr_frequency'] or uav.get('ktr_frequency', ''),
            'ktr_bandwidth': form_data['ktr_bandwidth'] or uav.get('ktr_bandwidth', ''),
            'ktr_modulation': form_data['ktr_modulation'] or uav.get('ktr_modulation', ''),
            'ktr_details': form_data['ktr_details'] or uav.get('ktr_details', ''),
            'video_frequency': form_data['video_frequency'] or uav.get('video_frequency', ''),
            'video_bandwidth': form_data['video_bandwidth'] or uav.get('video_bandwidth', ''),
            'video_modulation': form_data['video_modulation'] or uav.get('video_modulation', ''),
            'avatar': avatar_name or uav.get('avatar', ''),
            'spectrum': spectrum_name or uav.get('spectrum', ''),
            'extra_photos': extra_photos
        }

        uav_database = load_db()
        uav_database = [updated_uav if item['id'] == uav_id else item for item in uav_database]
        save_db(uav_database)

        flash('Інформацію про БПЛА оновлено.', 'success')
        return redirect(url_for('admin_panel'))

    return render_template('uav_form.html', uav=uav, form_title='Редагувати БПЛА', submit_text='Оновити', form_action=url_for('edit_uav', uav_id=uav_id))


@app.route('/delete/<int:uav_id>', methods=['POST'])
@admin_required
def delete_uav(uav_id):
    uav_database = load_db()
    uav = get_uav_by_id(uav_id)
    if uav is None:
        flash('Запис не знайдено.', 'error')
        return redirect(url_for('admin_panel'))

    for filename in [uav.get('avatar'), uav.get('spectrum')] + uav.get('extra_photos', []):
        remove_file(filename)

    uav_database = [item for item in uav_database if item['id'] != uav_id]
    save_db(uav_database)

    flash('Запис успішно видалено.', 'success')
    return redirect(url_for('admin_panel'))


@app.errorhandler(413)
def request_entity_too_large(error):
    flash('Файл занадто великий. Максимальний розмір — 16 МБ.', 'error')
    return redirect(request.referrer or url_for('admin_panel'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=False)

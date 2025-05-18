from flask import Flask, render_template, request, redirect, url_for, flash, Response, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import datetime
import os
import unicodedata
import re
import scrapers
from ics import Calendar, Event as ICSEvent
from fpdf import FPDF

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY',
                                          'alapertelmezett_nagyon_biztonsagos_kulcs_csrf_hez_es_sessionhoz')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'musorfigyelo.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
login_manager.login_message = "A tartalom megtekintéséhez kérjük jelentkezzen be."


def slugify(value, allow_unicode=False):
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize('NFKC', value)
    else:
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^\w\s-]', '', value.lower())
    return re.sub(r'[-\s]+', '-', value).strip('-_')


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    fullname = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    lists = db.relationship('UserList', backref='owner', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.fullname} ({self.email})>"


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    venue = db.Column(db.String(150), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(20))
    time = db.Column(db.String(10))
    price = db.Column(db.Float)
    description = db.Column(db.Text, nullable=True)
    booking_url = db.Column(db.String(300), nullable=True)
    source = db.Column(db.String(100))
    source_event_id = db.Column(db.String(100), unique=True, nullable=True)
    poster_url = db.Column(db.String(300), nullable=True)

    def __repr__(self):
        return f"<Event {self.id}: {self.title} at {self.venue} on {self.date}>"


class UserList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    items = db.relationship('ListItem', backref='user_list_ref', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<UserList {self.name}>"


class ListItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_list_id = db.Column(db.Integer, db.ForeignKey('user_list.id'), nullable=False)
    event_title_slug = db.Column(db.String(255), nullable=False)
    event_title_display = db.Column(db.String(200), nullable=True)
    event_poster_url_display = db.Column(db.String(300), nullable=True)
    added_on = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_list_id', 'event_title_slug', name='_user_list_event_uc'),)

    def __repr__(self):
        return f"<ListItem event_slug:{self.event_title_slug} in list:{self.user_list_id}>"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


class RegistrationForm(FlaskForm):
    fullname = StringField('Teljes név', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email cím', validators=[DataRequired(), Email(message="Érvényes email címet adjon meg.")])
    password = PasswordField('Jelszó', validators=[DataRequired(), Length(min=6,
                                                                          message="A jelszónak legalább 6 karakter hosszúnak kell lennie.")])
    confirm_password = PasswordField('Jelszó megerősítése', validators=[DataRequired(), EqualTo('password',
                                                                                                message='A két jelszónak egyeznie kell.')])
    submit = SubmitField('Regisztráció')

    def validate_email(self, email_field):
        user = User.query.filter_by(email=email_field.data).first()
        if user:
            raise ValidationError('Ez az email cím már foglalt. Kérjük, válasszon másikat.')


class LoginForm(FlaskForm):
    email = StringField('Email cím', validators=[DataRequired(), Email(message="Érvényes email címet adjon meg.")])
    password = PasswordField('Jelszó', validators=[DataRequired()])
    remember = BooleanField('Emlékezz rám')
    submit = SubmitField('Bejelentkezés')


class CreateListForm(FlaskForm):
    name = StringField('Lista neve', validators=[DataRequired(), Length(min=1, max=100)])
    submit = SubmitField('Lista létrehozása')


class AddToListForm(FlaskForm):
    user_list = SelectField('Válassz listát', coerce=int, validators=[Optional()])
    new_list_name = StringField('Vagy hozz létre újat', validators=[Optional(), Length(max=100)])
    submit_add = SubmitField('Hozzáadás a listához')


@app.context_processor
def inject_current_year():
    return {'current_year': datetime.datetime.now().year}


@app.route('/')
def index():
    all_events_query = Event.query.order_by(Event.title, Event.date, Event.time)
    event_groups_dict = {}
    for event in all_events_query.all():
        if event.title not in event_groups_dict:
            event_groups_dict[event.title] = {
                'representative_event': event,
                'slug': slugify(event.title)
            }
    return render_template('index.html', event_groups=list(event_groups_dict.values()), page_title="Főoldal")


@app.route('/search', endpoint='search_page')
def search_results_page():
    query_term = request.args.get('query', '').lower()
    city_filter = request.args.get('city', '').lower()
    query_builder = Event.query
    if query_term:
        query_builder = query_builder.filter(
            db.or_(Event.title.ilike(f'%{query_term}%'), Event.description.ilike(f'%{query_term}%')))
    if city_filter:
        query_builder = query_builder.filter(Event.city.ilike(f'%{city_filter}%'))
    results_query = query_builder.order_by(Event.title, Event.date, Event.time).all()
    event_groups_dict = {}
    for event in results_query:
        if event.title not in event_groups_dict:
            event_groups_dict[event.title] = {'representative_event': event, 'slug': slugify(event.title)}
    return render_template('search_results.html', event_groups=list(event_groups_dict.values()), query=query_term,
                           city=city_filter, page_title="Keresési Eredmények")


@app.route('/film/<event_title_slug>', methods=['GET', 'POST'])
def film_detail_grouped(event_title_slug):
    all_db_events = Event.query.order_by(Event.date, Event.time).all()
    events_for_title = []
    film_actual_title = None
    representative_event_for_display = None

    for event_in_db in all_db_events:
        if slugify(event_in_db.title) == event_title_slug:
            if not film_actual_title:
                film_actual_title = event_in_db.title
                representative_event_for_display = event_in_db
            events_for_title.append(event_in_db)

    if not events_for_title:
        flash('A keresett film/előadás nem található.', 'danger')
        return redirect(url_for('index'))

    add_to_list_form = AddToListForm()
    if current_user.is_authenticated:
        add_to_list_form.user_list.choices = [(lst.id, lst.name) for lst in
                                              UserList.query.filter_by(user_id=current_user.id).order_by(
                                                  UserList.name).all()]
        add_to_list_form.user_list.choices.insert(0, (0, "--- Válassz listát ---"))

    if add_to_list_form.validate_on_submit() and add_to_list_form.submit_add.data:
        if not current_user.is_authenticated:
            flash("A listához adáshoz be kell jelentkezned.", "warning")
            return redirect(url_for('login', next=request.url))

        list_id = add_to_list_form.user_list.data
        new_list_name = add_to_list_form.new_list_name.data.strip()
        target_list = None

        if new_list_name:
            existing_list_by_name = UserList.query.filter_by(user_id=current_user.id, name=new_list_name).first()
            if existing_list_by_name:
                flash(f"'{new_list_name}' nevű lista már létezik. Az elem ehhez lett hozzáadva.", "info")
                target_list = existing_list_by_name
            else:
                target_list = UserList(name=new_list_name, owner=current_user)
                db.session.add(target_list)
                flash(f"Új lista létrehozva: '{new_list_name}'.", "success")
        elif list_id and list_id != 0:
            target_list = UserList.query.filter_by(id=list_id, user_id=current_user.id).first()
            if not target_list:
                flash("A kiválasztott lista nem található.", "danger")
                return redirect(url_for('film_detail_grouped', event_title_slug=event_title_slug))
        else:
            flash("Válassz egy listát vagy adj meg egy új lista nevet.", "warning")

        if target_list:
            existing_item = ListItem.query.filter_by(user_list_id=target_list.id,
                                                     event_title_slug=event_title_slug).first()
            if existing_item:
                flash(f"'{film_actual_title}' már szerepel a '{target_list.name}' listán.", "info")
            else:
                list_item = ListItem(
                    user_list_ref=target_list,  # SQLAlchemy automatikusan beállítja a user_list_id-t
                    event_title_slug=event_title_slug,
                    event_title_display=film_actual_title,
                    event_poster_url_display=representative_event_for_display.poster_url if representative_event_for_display else None
                )
                db.session.add(list_item)
                try:
                    db.session.commit()
                    flash(f"'{film_actual_title}' hozzáadva a '{target_list.name}' listához.", "success")
                except Exception as e:
                    db.session.rollback()
                    flash(f"Hiba történt a listához adás közben: {e}", "danger")
            return redirect(url_for('film_detail_grouped', event_title_slug=event_title_slug))

    venues_showtimes_grouped = {}
    for event in events_for_title:
        venue_key = (event.venue, event.city)
        if venue_key not in venues_showtimes_grouped:
            venues_showtimes_grouped[venue_key] = {'venue_name': event.venue, 'city_name': event.city,
                                                   'showings_by_date': {}}
        if event.date not in venues_showtimes_grouped[venue_key]['showings_by_date']:
            venues_showtimes_grouped[venue_key]['showings_by_date'][event.date] = []
        venues_showtimes_grouped[venue_key]['showings_by_date'][event.date].append(
            {'time': event.time, 'event_id': event.id, 'booking_url': event.booking_url})
        venues_showtimes_grouped[venue_key]['showings_by_date'][event.date].sort(key=lambda x: x['time'])
    for venue_data in venues_showtimes_grouped.values():
        venue_data['showings_by_date'] = dict(sorted(venue_data['showings_by_date'].items()))

    return render_template('event_detail_grouped.html',
                           film_title=film_actual_title,
                           poster_url=representative_event_for_display.poster_url if representative_event_for_display else None,
                           description=representative_event_for_display.description if representative_event_for_display else "Leírás nem elérhető.",
                           venues_data=list(venues_showtimes_grouped.values()),
                           page_title=film_actual_title,
                           add_to_list_form=add_to_list_form,
                           event_title_slug=event_title_slug)


@app.route('/my-lists', methods=['GET', 'POST'])
@login_required
def my_lists():
    create_list_form = CreateListForm()
    if create_list_form.validate_on_submit() and create_list_form.submit.data:  # Ellenőrizzük, hogy a helyes gomb lett-e megnyomva
        list_name = create_list_form.name.data.strip()
        existing_list = UserList.query.filter_by(user_id=current_user.id, name=list_name).first()
        if existing_list:
            flash('Már létezik ilyen nevű listád.', 'warning')
        else:
            new_list = UserList(name=list_name, owner=current_user)
            db.session.add(new_list)
            db.session.commit()
            flash(f"'{list_name}' lista sikeresen létrehozva.", 'success')
        return redirect(url_for('my_lists'))

    user_lists = UserList.query.filter_by(user_id=current_user.id).order_by(UserList.name).all()
    return render_template('my_lists.html', page_title="Listáim", lists=user_lists, form=create_list_form)


@app.route('/list/<int:list_id>')
@login_required
def list_detail(list_id):
    user_list = UserList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    list_items_details = []
    for item in user_list.items:
        list_items_details.append({
            'item_id': item.id,
            'title': item.event_title_display,
            'poster_url': item.event_poster_url_display,
            'slug': item.event_title_slug,
            'added_on': item.added_on.strftime('%Y-%m-%d') if item.added_on else 'N/A'
        })
    return render_template('list_detail.html', page_title=user_list.name, current_list=user_list,
                           items_details=list_items_details)


@app.route('/remove-from-list/<int:list_item_id>', methods=['POST'])
@login_required
def remove_from_list(list_item_id):
    item_to_delete = ListItem.query.get_or_404(list_item_id)
    if item_to_delete.user_list_ref.user_id != current_user.id:
        flash('Nincs jogosultságod ennek az elemnek a törléséhez.', 'danger')
        return redirect(url_for('my_lists'))
    list_id_redirect = item_to_delete.user_list_id
    db.session.delete(item_to_delete)
    db.session.commit()
    flash('Elem sikeresen eltávolítva a listáról.', 'success')
    return redirect(url_for('list_detail', list_id=list_id_redirect))


@app.route('/delete-list/<int:list_id>', methods=['POST'])
@login_required
def delete_list(list_id):
    list_to_delete = UserList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    db.session.delete(list_to_delete)
    db.session.commit()
    flash(f"'{list_to_delete.name}' lista sikeresen törölve.", 'success')
    return redirect(url_for('my_lists'))


# --- Export útvonalak ---
def parse_event_datetime(date_str, time_str):
    try:
        dt_obj_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        dt_obj_time = datetime.datetime.strptime(time_str, '%H:%M').time()
        return datetime.datetime.combine(dt_obj_date.date(), dt_obj_time)
    except ValueError:
        print(f"Hiba a dátum/idő parse-olásakor: date='{date_str}', time='{time_str}'")
        return None


@app.route('/list/<int:list_id>/export/ics')
@login_required
def export_list_ics(list_id):
    user_list = UserList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()
    cal = Calendar()

    for item in user_list.items:
        events_for_item = Event.query.filter(
            Event.title == item.event_title_display).all()

        for concrete_event in events_for_item:
            if concrete_event.date == "N/A" or concrete_event.time == "N/A":
                continue

            start_dt = parse_event_datetime(concrete_event.date, concrete_event.time)
            if not start_dt:
                continue

            duration = datetime.timedelta(hours=2)
            if concrete_event.event_type == "Színház":
                duration = datetime.timedelta(hours=3)

            end_dt = start_dt + duration

            ics_e = ICSEvent()
            ics_e.name = concrete_event.title
            ics_e.begin = start_dt
            ics_e.end = end_dt
            ics_e.location = f"{concrete_event.venue}, {concrete_event.city}"
            description_parts = [concrete_event.description or ""]
            if concrete_event.booking_url:
                description_parts.append(f"Jegyvásárlás: {concrete_event.booking_url}")
            ics_e.description = "\n".join(filter(None, description_parts))

            cal.events.add(ics_e)

    if not cal.events:
        flash("A listához nem tartoznak exportálható események (nincs érvényes dátum/idő).", "warning")
        return redirect(url_for('list_detail', list_id=list_id))

    response_data = str(cal)
    return Response(
        response_data,
        mimetype="text/calendar",
        headers={"Content-disposition": f"attachment; filename={slugify(user_list.name)}.ics"}
    )


class PDF(FPDF):
    def header(self):
        self.add_font('DejaVu', '', 'DejaVuSansCondensed.ttf', uni=True)
        self.set_font('DejaVu', '', 15)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', '', 8)
        self.cell(0, 10, f'Oldal {self.page_no()}/{{nb}}', 0, 0, 'C')

    def chapter_title(self, title):
        self.set_font('DejaVu', '', 12)
        self.set_fill_color(200, 220, 255)
        self.cell(0, 6, title, 0, 1, 'L', 1)
        self.ln(4)

    def chapter_body(self, body_text):
        self.set_font('DejaVu', '', 10)
        self.multi_cell(0, 5, body_text)
        self.ln()

    def add_event_details(self, event_title, showings):
        self.set_font('DejaVu', '', 11)
        self.cell(0, 7, f"Film/Előadás: {event_title}", 0, 1, 'L')

        self.set_font('DejaVu', '', 9)
        if showings:
            for venue_city, date_times in showings.items():
                venue, city = venue_city
                self.cell(10)  # Behúzás
                self.multi_cell(0, 5, f"Helyszín: {venue} ({city})")
                for date, times in date_times.items():
                    self.cell(20)  # További behúzás
                    self.multi_cell(0, 5, f"    Dátum: {date} - Időpontok: {', '.join(t['time'] for t in times)}")
        else:
            self.cell(10)
            self.multi_cell(0, 5, "Nincsenek elérhető vetítések/előadások ehhez a címhez az adatbázisban.")
        self.ln(3)


@app.route('/list/<int:list_id>/export/pdf')
@login_required
def export_list_pdf(list_id):
    user_list = UserList.query.filter_by(id=list_id, user_id=current_user.id).first_or_404()

    pdf = PDF()
    pdf.alias_nb_pages()
    try:
        font_path = os.path.join(app.static_folder, 'fonts', 'DejaVuSansCondensed.ttf')
        if not os.path.exists(font_path):
            font_path = 'DejaVuSansCondensed.ttf'
        pdf.add_font('DejaVu', '', font_path, uni=True)
    except RuntimeError as e:
        print(f"FPDF Hiba: Nem sikerült betölteni a DejaVu fontot. ({e}) Használom az alapértelmezettet.")
        flash("Hiba a PDF generálásakor: Betűtípus nem található. Az ékezetek hibásan jelenhetnek meg.", "warning")

    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font('DejaVu', '', 18)
    try:
        list_name_encoded = user_list.name
    except AttributeError:
        list_name_encoded = user_list.name.encode('latin-1', 'replace').decode('latin-1')

    pdf.cell(0, 10, list_name_encoded, 0, 1, 'C')
    pdf.ln(10)

    if not user_list.items:
        pdf.set_font('DejaVu', '', 12)
        pdf.cell(0, 10, "Ez a lista jelenleg üres.", 0, 1, 'C')

    for item in user_list.items:
        pdf.chapter_title(item.event_title_display or "Ismeretlen esemény")

        concrete_events_for_item = Event.query.filter(Event.title == item.event_title_display).order_by(Event.venue,
                                                                                                        Event.date,
                                                                                                        Event.time).all()

        showings_by_venue_date = {}
        if concrete_events_for_item:
            for ce in concrete_events_for_item:
                venue_city_key = (ce.venue, ce.city)
                if venue_city_key not in showings_by_venue_date:
                    showings_by_venue_date[venue_city_key] = {}
                if ce.date not in showings_by_venue_date[venue_city_key]:
                    showings_by_venue_date[venue_city_key][ce.date] = []
                showings_by_venue_date[venue_city_key][ce.date].append({'time': ce.time, 'booking_url': ce.booking_url})

        pdf.add_event_details(item.event_title_display or "Cím nélküli esemény", showings_by_venue_date)
        pdf.ln(5)

    pdf_output = pdf.output(dest='S').encode('latin-1')

    response = make_response(pdf_output)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={slugify(user_list.name)}.pdf'
    return response


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(fullname=form.fullname.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'Sikeres regisztráció, {form.fullname.data}! Most már bejelentkezhetsz.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', page_title='Regisztráció', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash('Sikeresen bejelentkeztél!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Sikertelen bejelentkezés. Kérjük, ellenőrizd az email címed és a jelszavad.', 'danger')
    return render_template('login.html', page_title='Bejelentkezés', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Sikeresen kijelentkeztél.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', page_title='Irányítópult')


@app.route('/admin/update-events')
@login_required
def update_events_from_scrapers():
    if not current_user.email == 'admin@example.com':
        flash('Nincs jogosultságod ehhez a művelethez.', 'danger')
        return redirect(url_for('index'))

    print("DEBUG: Starting event update process...")
    flash('Események frissítése elkezdődött...', 'info')

    try:
        num_rows_deleted = db.session.query(Event).delete()
        db.session.commit()
        print(f"DEBUG: {num_rows_deleted} old events deleted.")
        flash(f'{num_rows_deleted} régi esemény törölve.', 'info')
    except Exception as e:
        db.session.rollback()
        print(f"ERROR: Deleting old events failed: {e}")
        flash(f'Hiba a régi események törlése közben: {e}', 'danger')
        return redirect(url_for('dashboard'))

    cinema_city_events = scrapers.scrape_cinema_city()
    nemzeti_szinhaz_events = scrapers.scrape_nemzeti_szinhaz()

    print(f"DEBUG: Cinema City events scraped: {len(cinema_city_events)}")
    print(f"DEBUG: Nemzeti Szinhaz events scraped: {len(nemzeti_szinhaz_events)}")

    all_scraped_events = cinema_city_events + nemzeti_szinhaz_events

    new_events_count = 0
    failed_events_count = 0
    processed_source_event_ids = set()

    for event_data in all_scraped_events:

        source_event_id_str = str(event_data.get('source_event_id')) if event_data.get('source_event_id') else None

        if not source_event_id_str:
            failed_events_count += 1
            continue

        if source_event_id_str in processed_source_event_ids:
            failed_events_count += 1
            continue

        required_keys = ['title', 'type', 'venue', 'city', 'date', 'time', 'source']
        if not all(k in event_data and event_data[k] for k in required_keys):
            failed_events_count += 1
            continue

        event = Event(
            title=event_data.get('title'),
            event_type=event_data.get('type'),
            venue=event_data.get('venue'),
            city=event_data.get('city'),
            date=event_data.get('date'),
            time=event_data.get('time'),
            price=float(event_data.get('price')) if event_data.get('price') is not None else None,
            description=event_data.get('description'),
            booking_url=event_data.get('booking_url'),
            source=event_data.get('source'),
            source_event_id=source_event_id_str,
            poster_url=event_data.get('poster_url')
        )
        db.session.add(event)
        processed_source_event_ids.add(source_event_id_str)
        new_events_count += 1

    if new_events_count > 0:
        try:
            db.session.commit()
            flash(f'{new_events_count} új esemény sikeresen hozzáadva az adatbázishoz.', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"ERROR: Committing new events to DB failed: {e}")
            flash(f'Hiba történt az események adatbázisba mentése közben: {e}', 'danger')
            new_events_count_before_fail = new_events_count
            new_events_count = 0
            failed_events_count += new_events_count_before_fail
    else:
        if not all_scraped_events:
            flash('Nem sikerült adatokat gyűjteni a forrásokból.', 'warning')
        elif failed_events_count == len(all_scraped_events) and len(all_scraped_events) > 0:
            flash('Minden begyűjtött adat hibás volt, nem került új esemény az adatbázisba.', 'warning')
        else:
            flash('Nem található érvényes új esemény a frissítés során.', 'info')

    if failed_events_count > 0:
        flash(f'{failed_events_count} eseményt nem sikerült feldolgozni vagy hozzáadni.', 'warning')

    print("DEBUG: Event update process finished.")
    return redirect(url_for('index'))


def create_tables():
    with app.app_context():
        db.create_all()


if __name__ == '__main__':
    create_tables()
    app.run(debug=True)

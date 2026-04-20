from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, ForeignKey, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from datetime import datetime
import os

# Глобальная переменная для пути к БД
_db_path = "data.db"
_engine = None
_Session = None


def set_db_path(db_path):
    """Устанавливает новый путь к базе данных и пересоздаёт соединение"""
    global _db_path, _engine, _Session, Base

    _db_path = db_path

    # Создаём директорию, если её нет
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    # Создаём новый engine
    _engine = create_engine(f"sqlite:///{db_path}")

    # Пересоздаём таблицы и выполняем миграцию
    Base.metadata.create_all(_engine)
    _migrate_database()

    # Создаём новую сессию
    _Session = sessionmaker(bind=_engine)


def get_engine():
    """Возвращает текущий engine"""
    global _engine
    if _engine is None:
        set_db_path(_db_path)
    return _engine


def get_session():
    """Возвращает новую сессию"""
    global _Session
    if _Session is None:
        set_db_path(_db_path)
    return _Session()


# Инициализация по умолчанию
Base = declarative_base()


# --- Модель организации ---
class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    inn = Column(String)
    kpp = Column(String)
    bik = Column(String)
    rs = Column(String)
    legal_address = Column(String, default="")
    ogrn = Column(String, default="")

    invoices = relationship("Invoice", back_populates="company", cascade="all, delete-orphan")


# --- Модель счёта ---
class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    invoice_number = Column(String)
    company_id = Column(Integer, ForeignKey("companies.id"))
    company_name = Column(String)
    total_amount = Column(Float)
    items = Column(String)
    configuration = Column(String, default="")
    file_path = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    markup_percent = Column(Float, default=0.0)
    delivery_cost = Column(Float, default=0.0)

    company = relationship("Company", back_populates="invoices")


# --- Модель настроек ---
class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True)
    value = Column(String)


def _migrate_database():
    """Автоматически добавляет недостающие колонки в существующую БД"""
    inspector = inspect(get_engine())

    if inspector.has_table("companies"):
        columns = [col["name"] for col in inspector.get_columns("companies")]

        if "legal_address" not in columns:
            with get_engine().connect() as conn:
                conn.execute(text("ALTER TABLE companies ADD COLUMN legal_address TEXT DEFAULT ''"))
                conn.commit()

        if "ogrn" not in columns:
            with get_engine().connect() as conn:
                conn.execute(text("ALTER TABLE companies ADD COLUMN ogrn TEXT DEFAULT ''"))
                conn.commit()

    if inspector.has_table("invoices"):
        columns = [col["name"] for col in inspector.get_columns("invoices")]

        if "markup_percent" not in columns:
            with get_engine().connect() as conn:
                conn.execute(text("ALTER TABLE invoices ADD COLUMN markup_percent FLOAT DEFAULT 0.0"))
                conn.commit()

        if "delivery_cost" not in columns:
            with get_engine().connect() as conn:
                conn.execute(text("ALTER TABLE invoices ADD COLUMN delivery_cost FLOAT DEFAULT 0.0"))
                conn.commit()

    if not inspector.has_table("settings"):
        Base.metadata.create_all(get_engine(), tables=[Setting.__table__])


# Инициализация
set_db_path("data.db")


# ==================== РАБОТА С ОРГАНИЗАЦИЯМИ ====================

def save_company(data):
    """Сохраняет организацию в базу данных"""
    session = get_session()
    try:
        company = Company(
            name=data.get("name", data.get("Название", "")),
            inn=data.get("inn", data.get("ИНН", "")),
            kpp=data.get("kpp", data.get("КПП", "")),
            bik=data.get("bik", data.get("БИК", "")),
            rs=data.get("rs", data.get("Р/С", "")),
            legal_address=data.get("legal_address", data.get("Адрес", data.get("Юридический адрес", ""))),
            ogrn=data.get("ogrn", data.get("ОГРН", ""))
        )
        session.add(company)
        session.commit()
        return company
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_companies():
    """Возвращает список всех организаций"""
    session = get_session()
    try:
        companies = session.query(Company).order_by(Company.name).all()
        return companies
    finally:
        session.close()


def get_company_by_id(company_id):
    """Возвращает организацию по ID"""
    session = get_session()
    try:
        company = session.query(Company).filter(Company.id == company_id).first()
        return company
    finally:
        session.close()


def get_company_by_name(name):
    """Возвращает организацию по названию"""
    session = get_session()
    try:
        company = session.query(Company).filter(Company.name == name).first()
        return company
    finally:
        session.close()


def update_company(company_id, data):
    """Обновляет данные организации"""
    session = get_session()
    try:
        company = session.query(Company).filter(Company.id == company_id).first()
        if company:
            company.name = data.get("name", company.name)
            company.inn = data.get("inn", company.inn)
            company.kpp = data.get("kpp", company.kpp)
            company.bik = data.get("bik", company.bik)
            company.rs = data.get("rs", company.rs)
            company.legal_address = data.get("legal_address", company.legal_address)
            company.ogrn = data.get("ogrn", company.ogrn)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def delete_company(company_id):
    """Удаляет организацию и все связанные с ней счета"""
    session = get_session()
    try:
        company = session.query(Company).filter(Company.id == company_id).first()
        if company:
            for invoice in company.invoices:
                session.delete(invoice)
            session.delete(company)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_companies_count():
    """Возвращает количество организаций в базе"""
    session = get_session()
    try:
        count = session.query(Company).count()
        return count
    finally:
        session.close()


# ==================== РАБОТА СО СЧЕТАМИ ====================

def save_invoice(data):
    """Сохраняет счёт в базу данных"""
    session = get_session()
    try:
        invoice = Invoice(
            invoice_number=str(data.get("invoice_number", "")),
            company_id=data.get("company_id"),
            company_name=data.get("company_name", ""),
            total_amount=float(data.get("total_amount", 0)),
            items=str(data.get("items", "[]")),
            configuration=data.get("configuration", ""),
            file_path=data.get("file_path", ""),
            markup_percent=float(data.get("markup_percent", 0.0)),
            delivery_cost=float(data.get("delivery_cost", 0.0))
        )
        session.add(invoice)
        session.commit()
        return invoice
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_invoices():
    """Возвращает список всех счетов (сортировка по дате - новые сверху)"""
    session = get_session()
    try:
        invoices = session.query(Invoice).order_by(Invoice.created_at.desc()).all()
        return invoices
    finally:
        session.close()


def get_invoice_by_id(invoice_id):
    """Возвращает счёт по ID"""
    session = get_session()
    try:
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        return invoice
    finally:
        session.close()


def get_invoices_by_company(company_id):
    """Возвращает все счета для конкретной организации"""
    session = get_session()
    try:
        invoices = session.query(Invoice).filter(Invoice.company_id == company_id).order_by(
            Invoice.created_at.desc()).all()
        return invoices
    finally:
        session.close()


def get_invoices_by_number(invoice_number):
    """Возвращает счёт по номеру"""
    session = get_session()
    try:
        invoice = session.query(Invoice).filter(Invoice.invoice_number == str(invoice_number)).first()
        return invoice
    finally:
        session.close()


def update_invoice(invoice_id, data):
    """Обновляет данные счёта"""
    session = get_session()
    try:
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            if "company_name" in data:
                invoice.company_name = data["company_name"]
            if "total_amount" in data:
                invoice.total_amount = float(data["total_amount"])
            if "items" in data:
                invoice.items = str(data["items"])
            if "configuration" in data:
                invoice.configuration = data["configuration"]
            if "file_path" in data:
                invoice.file_path = data["file_path"]
            if "markup_percent" in data:
                invoice.markup_percent = float(data["markup_percent"])
            if "delivery_cost" in data:
                invoice.delivery_cost = float(data["delivery_cost"])
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def delete_invoice(invoice_id):
    """Удаляет счёт"""
    session = get_session()
    try:
        invoice = session.query(Invoice).filter(Invoice.id == invoice_id).first()
        if invoice:
            session.delete(invoice)
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_invoices_count():
    """Возвращает количество счетов в базе"""
    session = get_session()
    try:
        count = session.query(Invoice).count()
        return count
    finally:
        session.close()


def get_total_invoices_amount():
    """Возвращает общую сумму всех счетов"""
    session = get_session()
    try:
        total = session.query(Invoice.total_amount).all()
        return sum(t[0] for t in total) if total else 0
    finally:
        session.close()


def get_next_invoice_number():
    """Возвращает следующий номер счёта"""
    session = get_session()
    try:
        last_invoice = session.query(Invoice).order_by(Invoice.id.desc()).first()
        if last_invoice and last_invoice.invoice_number:
            try:
                return int(last_invoice.invoice_number) + 1
            except ValueError:
                return 24045
        return 24044
    finally:
        session.close()


def search_invoices(search_text):
    """Поиск счетов по номеру или названию организации"""
    session = get_session()
    try:
        invoices = session.query(Invoice).filter(
            (Invoice.invoice_number.contains(search_text)) |
            (Invoice.company_name.contains(search_text))
        ).order_by(Invoice.created_at.desc()).all()
        return invoices
    finally:
        session.close()


# ==================== РАБОТА С НАСТРОЙКАМИ ====================

def get_setting(key, default=None):
    """Получает значение настройки"""
    session = get_session()
    try:
        setting = session.query(Setting).filter(Setting.key == key).first()
        return setting.value if setting else default
    finally:
        session.close()


def save_setting(key, value):
    """Сохраняет значение настройки"""
    session = get_session()
    try:
        setting = session.query(Setting).filter(Setting.key == key).first()
        if setting:
            setting.value = str(value)
        else:
            setting = Setting(key=key, value=str(value))
            session.add(setting)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def get_all_settings():
    """Возвращает все настройки"""
    session = get_session()
    try:
        settings = session.query(Setting).all()
        return {s.key: s.value for s in settings}
    finally:
        session.close()


def delete_setting(key):
    """Удаляет настройку"""
    session = get_session()
    try:
        setting = session.query(Setting).filter(Setting.key == key).first()
        if setting:
            session.delete(setting)
            session.commit()
            return True
        return False
    finally:
        session.close()


def get_db_path():
    """Возвращает текущий путь к базе данных"""
    global _db_path
    return _db_path


# ==================== СТАТИСТИКА ====================

def get_statistics():
    """Возвращает общую статистику по системе"""
    session = get_session()
    try:
        companies_count = session.query(Company).count()
        invoices_count = session.query(Invoice).count()
        total_amount = session.query(Invoice.total_amount).all()
        total_sum = sum(t[0] for t in total_amount) if total_amount else 0

        from sqlalchemy import func
        monthly_stats = session.query(
            func.strftime('%Y-%m', Invoice.created_at).label('month'),
            func.count(Invoice.id).label('count'),
            func.sum(Invoice.total_amount).label('total')
        ).group_by(func.strftime('%Y-%m', Invoice.created_at)).all()

        return {
            "companies_count": companies_count,
            "invoices_count": invoices_count,
            "total_amount": total_sum,
            "average_amount": total_sum / invoices_count if invoices_count > 0 else 0,
            "monthly_stats": monthly_stats
        }
    finally:
        session.close()


# ==================== ОЧИСТКА ДАННЫХ ====================

def clear_all_data():
    """Удаляет все данные из базы (осторожно!)"""
    session = get_session()
    try:
        session.query(Invoice).delete()
        session.query(Company).delete()
        session.query(Setting).delete()
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise e
    finally:
        session.close()


def vacuum_database():
    """Оптимизирует базу данных SQLite"""
    with get_engine().connect() as conn:
        conn.execute(text("VACUUM"))
        conn.commit()
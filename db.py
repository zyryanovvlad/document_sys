from sqlalchemy import create_engine, Column, String, Integer
from sqlalchemy.orm import declarative_base, sessionmaker

engine = create_engine("sqlite:///data.db")
Base = declarative_base()

class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    inn = Column(String)
    kpp = Column(String)
    bik = Column(String)
    rs = Column(String)

Base.metadata.create_all(engine)

Session = sessionmaker(bind=engine)

def save_company(data):
    session = Session()

    company = Company(
        name=data["Название"],
        inn=data["ИНН"],
        kpp=data["КПП"],
        bik=data["БИК"],
        rs=data["Р/С"]
    )

    session.add(company)
    session.commit()
    session.close()

def get_companies():
    session = Session()
    data = session.query(Company).all()
    session.close()
    return data
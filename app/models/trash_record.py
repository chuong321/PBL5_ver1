"""Database models for trash classification."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class TrashRecord(Base):
    """Trash classification record."""

    __tablename__ = "trash_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    image_path = Column(String(255), nullable=False)
    label = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    has_liquid = Column(String(10), nullable=True)
    weight_grams = Column(Float, nullable=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)

    individual_confidences = Column(String(255), nullable=True)
    primary_model_output = Column(String(255), nullable=True)
    secondary_model_output = Column(String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<TrashRecord {self.id}: {self.label} "
            f"({self.confidence:.2%}) liquid={self.has_liquid}>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "image_path": self.image_path,
            "label": self.label,
            "confidence": f"{self.confidence:.2%}",
            "has_liquid": self.has_liquid or "unknown",
            "weight_grams": self.weight_grams,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if self.timestamp
            else "N/A",
        }


def init_db(database_url: str):
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    return engine


def get_session_factory(database_url: str):
    engine = create_engine(database_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal

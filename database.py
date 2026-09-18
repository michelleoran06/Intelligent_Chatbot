from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./chatbot_audit.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ConversationLog(Base):
    __tablename__ = "conversation_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), nullable=False)
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=False)
    routed_to = Column(String(20), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

def save_log(user_id: str, query: str, response: str, score: float, routed_to: str):
    session = SessionLocal()
    try:
        log_entry = ConversationLog(
            user_id=user_id,
            query=query,
            response=response,
            confidence_score=score,
            routed_to=routed_to
        )
        session.add(log_entry)
        session.commit()
        session.refresh(log_entry)
        return log_entry.id
    finally:
        session.close()

def update_ticket(ticket_id: int, manual_response: str):
    session = SessionLocal()
    try:
        ticket = session.query(ConversationLog).filter(ConversationLog.id == ticket_id).first()
        if ticket:
            ticket.response = manual_response
            ticket.routed_to = "human_resolved"
            session.commit()
    finally:
        session.close()

def get_ticket(ticket_id: int):
    session = SessionLocal()
    try:
        ticket = session.query(ConversationLog).filter(ConversationLog.id == ticket_id).first()
        if ticket:
            return {"response": ticket.response, "routed_to": ticket.routed_to}
        return None
    finally:
        session.close()

def get_escalated_tickets():
    session = SessionLocal()
    try:
        tickets = session.query(ConversationLog).filter(ConversationLog.routed_to == 'human').order_by(ConversationLog.timestamp.desc()).all()
        return [
            {
                "id": t.id, 
                "user_id": t.user_id, 
                "query": t.query, 
                "timestamp": t.timestamp.isoformat()
            } 
            for t in tickets
        ]
    finally:
        session.close()
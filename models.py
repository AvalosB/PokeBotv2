import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    BigInteger,
    DateTime,
    ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import JSONB

# The Declarative Base is the central point for SQLAlchemy models.
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    discord_user_id = Column(BigInteger, nullable=False, unique=True, index=True)
    discord_username = Column(String, nullable=False)
    server_id = Column(BigInteger, nullable=False)
    server_name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Establishes a one-to-many relationship with CaughtPokemon
    caught_pokemon = relationship("CaughtPokemon", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, discord_username='{self.discord_username}')>"

class CaughtPokemon(Base):
    __tablename__ = 'caught_pokemon'

    id = Column(Integer, primary_key=True)
    # Foreign key to link back to the user
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Basic Pokemon info, based on your pokedex_api.py script
    pokemon_id = Column(Integer, nullable=False)
    pokemon_name = Column(String, nullable=False)
    pokemon_sprite_url = Column(String)
    pokemon_types = Column(JSONB) # Stores list of type dictionaries
    assigned_move_details = Column(JSONB) # Stores move details dictionary

    caught_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Establishes the many-to-one relationship back to User
    user = relationship("User", back_populates="caught_pokemon")

    def __repr__(self):
        return f"<CaughtPokemon(id={self.id}, pokemon_name='{self.pokemon_name}', user_id={self.user_id})>"
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Enum, DateTime
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from enum import Enum as PyEnum
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, List
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('AUTH_DB_USER')}:{os.getenv('AUTH_DB_PASSWORD')}"
    f"@{os.getenv('AUTH_DB_HOST')}:{os.getenv('AUTH_DB_PORT')}/{os.getenv('AUTH_DB_NAME')}"
)

# Настройка асинхронного движка
engine = create_async_engine(DATABASE_URL, echo=True)

# Асинхронная фабрика сессий
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Базовый класс для моделей
Base = declarative_base()

# Генератор сессий
async def get_db():
    async with SessionLocal() as session:
        yield session


class RoleEnum(str, PyEnum):
    user = "user"  # Обычный пользователь
    admin = "admin"  # Администратор
    moderator = "moderator"  # Модератор
    seller = "seller"  # Продавец


class UserBase(BaseModel):
    email: str
    is_active: bool = True
    loyalty_card_number: Optional[str] = None 

    class Config:
        orm_mode = True

class User(UserBase):
    id: int
    role: RoleEnum  

    class Config:
        orm_mode = True

class WishlistBase(BaseModel):
    product_id: int

    class Config:
        orm_mode = True

class Wishlist(WishlistBase):
    id: int
    user_id: int

    class Config:
        orm_mode = True

class OrderBase(BaseModel):
    status: str = "pending"
    created_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class Order(OrderBase):
    id: int
    user_id: int
    order_items: List["OrderItem"] = []

    class Config:
        orm_mode = True

class OrderItemBase(BaseModel):
    product_id: int
    quantity: int

    class Config:
        orm_mode = True

class OrderItem(OrderItemBase):
    id: int
    order_id: int

    class Config:
        orm_mode = True

class SellerBase(BaseModel):
    shop_name: str
    inn: Optional[str] = None
    description: Optional[str] = None

    class Config:
        orm_mode = True

class Seller(SellerBase):
    id: int
    user_id: int

    class Config:
        orm_mode = True

class SellerRegister(BaseModel):
    email: str
    password: str
    shop_name: str
    inn: Optional[str] = None
    description: Optional[str] = None


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)  
    role = Column(Enum(RoleEnum), default=RoleEnum.user)  

    wishlist = relationship("Wishlist", back_populates="user")

    orders = relationship("Order", back_populates="user")


class Wishlist(Base):
    __tablename__ = "wishlist"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(Integer, nullable=False)


    user = relationship("User", back_populates="wishlist")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)  
    status = Column(String, default="pending")  

    user = relationship("User", back_populates="orders")
    order_items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer,nullable=False)
    quantity = Column(Integer, default=1) 

    order = relationship("Order", back_populates="order_items")

class Seller(Base):
    __tablename__ = "sellers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    shop_name = Column(String, nullable=False)
    inn = Column(String, nullable=True)
    description = Column(String, nullable=True)

    user = relationship("User")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

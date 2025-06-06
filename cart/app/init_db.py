from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from pydantic import BaseModel
from typing import List
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('CART_DB_USER')}:{os.getenv('CART_DB_PASSWORD')}"
    f"@{os.getenv('CART_DB_HOST')}:{os.getenv('CART_DB_PORT')}/{os.getenv('CART_DB_NAME')}"
)

engine = create_async_engine(DATABASE_URL, echo=True)

SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with SessionLocal() as session:
        yield session



class CartItemBase(BaseModel):
    product_id: int
    quantity: int

class CartItemResponse(CartItemBase):
    id: int
    class Config:
        orm_mode = True

class CartResponse(BaseModel):
    id: int
    user_id: int
    items: List[CartItemResponse]
    
    class Config:
        orm_mode = True



class Cart(Base):
    __tablename__ = 'carts'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False)
    
    items = relationship("CartItem", back_populates="cart")

class CartItem(Base):
    __tablename__ = 'cart_items'
    
    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, ForeignKey("carts.id"))
    product_id = Column(Integer, nullable=False)
    quantity = Column(Integer, default=1)
    
    cart = relationship("Cart", back_populates="items")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

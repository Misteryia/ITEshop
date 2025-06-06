from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from pydantic import BaseModel
from typing import List, Optional
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('CATALOG_DB_USER')}:{os.getenv('CATALOG_DB_PASSWORD')}"
    f"@{os.getenv('CATALOG_DB_HOST')}:{os.getenv('CATALOG_DB_PORT')}/{os.getenv('CATALOG_DB_NAME')}"
)

engine = create_async_engine(DATABASE_URL, echo=True)
async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with async_session() as session:
        yield session

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    active = Column(Boolean, default=True)
    category_id = Column(Integer, ForeignKey("categories.id"))
    seller_id = Column(Integer)
    image = Column(String, nullable=True)
    
    category = relationship("Category", back_populates="products")
    reviews = relationship("Review", back_populates="product")
    questions = relationship("Question", back_populates="product")

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    rating = Column(Integer, nullable=False)
    comment = Column(String, nullable=True)
    product = relationship("Product", back_populates="reviews")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    question = Column(String, nullable=False)
    answer = Column(String, nullable=True)
    product = relationship("Product", back_populates="questions")

class RelatedProduct(Base):
    __tablename__ = "related_products"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    related_product_id = Column(Integer, ForeignKey("products.id"))
    product = relationship("Product", foreign_keys=[product_id])
    related_product = relationship("Product", foreign_keys=[related_product_id])

# Pydantic models
class CategorySchemas(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True
        orm_mode = True

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int
    active: bool
    category_id: int
    seller_id: int
    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    price: float
    stock: int
    active: bool
    category_id: int
    seller_id: int
    class Config:
        from_attributes = True

class Product(ProductBase):
    id: int
    category: Optional[CategorySchemas] = None
    image: Optional[str] = None
    class Config:
        from_attributes = True
        orm_mode = True

class Review(BaseModel):
    id: int
    rating: int
    comment: Optional[str] = None
    class Config:
        orm_mode = True

class Question(BaseModel):
    id: int
    question: str
    answer: Optional[str] = None
    class Config:
        orm_mode = True

class RelatedProductBase(BaseModel):
    product_id: int
    related_product_id: int
    class Config:
        orm_mode = True

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException
from init_db import Product, Category, ProductBase, Product as ProductSchema, CategorySchemas
from sqlalchemy.orm import selectinload
from metrics import db_metr

@db_metr(operation="fetch_all_products")
async def fetch_all_products(
    db: AsyncSession, 
    category: int = None, 
    search: str = '', 
    skip: int = 0, 
    limit: int = 1000
):
    query = select(Product).order_by(Product.name)
    
    if category:
        query = query.filter(Product.category_id == category)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    products = result.scalars().all()
    
    products_list = [ProductBase.from_orm(product) for product in products]
    return [product.dict() for product in products_list]

@db_metr(operation="fetch_product_by_id")
async def fetch_product_by_id(db: AsyncSession, product_id: int):
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .filter(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    return ProductSchema.from_orm(product) if product else None

@db_metr(operation="fetch_all_categories")
async def fetch_all_categories(db: AsyncSession):
    result = await db.execute(select(Category))
    categories = result.scalars().all()
    categories_list = [CategorySchemas.from_orm(category) for category in categories]
    return [category.dict() for category in categories_list]

@db_metr(operation="fetch_seller_by_id")
async def fetch_seller_by_id(db: AsyncSession, seller_id: int):
    pass

@db_metr(operation="add_new_product")
async def add_new_product(
    db: AsyncSession,
    name: str,
    description: str,
    price: float,
    stock: int,
    category_id: int,
    seller_id: int
):
    if price < 0 or stock < 0:
        raise HTTPException(status_code=400, detail="Price and stock must be non-negative.")
    
    new_product = Product(
        name=name,
        description=description,
        price=price,
        stock=stock,
        category_id=category_id,
        seller_id=seller_id
    )
    
    db.add(new_product)
    await db.commit()
    await db.refresh(new_product)
    
    loaded_product = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .filter(Product.id == new_product.id)
    )
    return loaded_product.scalar_one_or_none()

@db_metr(operation="modify_product")
async def modify_product(
    db: AsyncSession,
    product_id: int,
    name: str,
    description: str,
    price: float,
    stock: int
):
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .filter(Product.id == product_id)
    )
    product_model = result.scalar_one_or_none()

    if not product_model:
        raise HTTPException(status_code=404, detail="Product not found")
    if price < 0 or stock < 0:
        raise HTTPException(status_code=400, detail="Price and stock must be non-negative.")
    
    product_model.name = name
    product_model.description = description
    product_model.price = price
    product_model.stock = stock

    await db.commit()
    await db.refresh(product_model)

    return {
        "id": product_model.id,
        "name": product_model.name,
        "description": product_model.description,
        "price": product_model.price,
        "stock": product_model.stock,
        "category_id": product_model.category_id,
        "seller_id": product_model.seller_id,
        "active": product_model.active,
        "category": {
            "id": product_model.category.id,
            "name": product_model.category.name
        } if product_model.category else None,
        "image": product_model.image
    }

@db_metr(operation="remove_product")
async def remove_product(db: AsyncSession, product_id: int):
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.images))
        .filter(Product.id == product_id)
    )
    product_model = result.scalar_one_or_none()

    if not product_model:
        raise HTTPException(status_code=404, detail="Product not found")
    
    await db.delete(product_model)
    await db.commit()
    return product_id
from fastapi import FastAPI, Depends, HTTPException, Query, Body, Request
from sqlalchemy.ext.asyncio import AsyncSession
from init_db import get_db, init_db, ProductBase, Product as ProductSchema, ProductCreate 
from typing import AsyncGenerator
from functions import *
from fastapi.middleware.cors import CORSMiddleware
from log_dec import log_kafka
from metrics import metr_endpoint, api_metr
from tracing import setup_tracing
from trace_dec import trace_function
from elastic import add_product_to_index, find_products_by_query
from fastapi.security import OAuth2PasswordBearer
import jwt

SECRET_KEY = "your_secret_key"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("id")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_id
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

async def lifespan(app: FastAPI) -> AsyncGenerator:
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
tracer = setup_tracing(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:8003", "http://localhost:8004"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/metr")
@trace_function(name="get_metr", include_request=True)
async def metr():
    return await metr_endpoint()

@app.get("/api/products")
@log_kafka
@api_metr()
@trace_function(name="list_products", include_request=True)
async def list_products(
    searchquery: str = Query(default='', alias="search"),
    category: int = None,
    seller: int = None,
    db: AsyncSession = Depends(get_db)
):
    if searchquery:
        products = await find_products_by_query(searchquery)
        if category is not None:
            products = [p for p in products if p["category_id"] == category]
        if seller is not None:
            products = [p for p in products if p["seller_id"] == seller]
        return products
    else:
        products = await fetch_all_products(db, category, "")
        if seller is not None:
            products = [p for p in products if p["seller_id"] == seller]
        return products

@app.get("/api/categories")
@log_kafka
@api_metr()
@trace_function(name="get_categories", include_request=True)
async def get_categories(db: AsyncSession = Depends(get_db)):
    return await fetch_all_categories(db)

@app.get("/api/get_product")
@log_kafka
@api_metr()
@trace_function(name="get_product", include_request=True)
async def get_product(id: int = None, db: AsyncSession = Depends(get_db)):
    product = await fetch_product_by_id(db, id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.get("/api/get_seller")
@log_kafka
@api_metr()
@trace_function(name="get_seller", include_request=True)
async def get_seller(id: int = None, db: AsyncSession = Depends(get_db)):
    return await fetch_seller_by_id(db, id)

@app.get("/products/{product_id}", response_model=ProductSchema)
@log_kafka
@api_metr()
@trace_function(name="get_product_details", include_request=True)
async def get_product_details(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await fetch_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.post("/products", response_model=ProductSchema)
@log_kafka
@api_metr()
@trace_function(name="add_product", include_request=True)
async def add_product(
    product: ProductCreate, 
    db: AsyncSession = Depends(get_db)
):
    new_product = await add_new_product(
        db,
        name=product.name,
        description=product.description,
        price=product.price,
        stock=product.stock,
        category_id=product.category_id,
        seller_id=product.seller_id
    )
    product_for_indexing = ProductSchema.from_orm(new_product).dict()
    await add_product_to_index(product_for_indexing)
    return new_product

@app.put("/edit_product/{product_id}", response_model=ProductSchema)
@log_kafka
@api_metr()
@trace_function(name="update_product", include_request=True)
async def update_product(
    product_id: int, 
    product: ProductBase, 
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
):
    user_id = verify_token(token)
    existing_product = await fetch_product_by_id(db, product_id)
    
    if not existing_product:
        raise HTTPException(status_code=404, detail="Product not found")
    if existing_product['seller_id'] != user_id:
        raise HTTPException(status_code=403, detail="No permission to update this product")

    updated_product = await modify_product(
        db,
        product_id,
        name=product.name,
        description=product.description,
        price=product.price,
        stock=product.stock
    )
    await add_product_to_index(updated_product)
    return updated_product

@app.delete("/products/{product_id}")
@log_kafka
@api_metr()
@trace_function(name="delete_product", include_request=True)
async def delete_product(
    product_id: int, 
    token: str = Depends(oauth2_scheme), 
    db: AsyncSession = Depends(get_db)
):
    user_id = verify_token(token)
    existing_product = await fetch_product_by_id(db, product_id)
    
    if not existing_product:
        raise HTTPException(status_code=404, detail="Product not found")
    if existing_product['seller_id'] != user_id:
        raise HTTPException(status_code=403, detail="No permission to delete this product")

    deleted_product_id = await remove_product(db, product_id)
    return {"message": f"Product with ID {deleted_product_id} deleted successfully"}

@app.post("/api/products/decrement_stock")
@log_kafka
@api_metr()
@trace_function(name="decrement_stock", include_request=True)
async def decrement_stock(
    product_id: int = Body(...),
    quantity: int = Body(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Product).filter(Product.id == product_id))
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.stock < quantity:
        raise HTTPException(status_code=400, detail="Not enough stock")
    
    product.stock -= quantity
    await db.commit()
    await db.refresh(product)
    return {
        "success": True, 
        "product_id": product_id, 
        "new_stock": product.stock
    }

@app.post("/admin_delete_product")
@log_kafka
@api_metr()
@trace_function(name="admin_remove_product", include_request=True)
async def admin_remove_product(request: Request, db: AsyncSession = Depends(get_db)):
    data = await request.json()
    product_id = data.get("id")
    token = request.headers.get("Auth")
    
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    
    jwt_token = token.split(" ", 1)[1]
    try:
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])
        role = payload.get("role")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    if role not in ("admin", "RoleEnum.admin"):
        raise HTTPException(status_code=403, detail="Only admin can delete products")
    
    deleted_product_id = await remove_product(db, product_id)
    return {
        "success": True, 
        "deleted_product_id": deleted_product_id
    }
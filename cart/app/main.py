from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from init_db import get_db, init_db, CartItem, CartItemBase, CartResponse
from typing import AsyncGenerator
from functions import *
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.future import select
from fastapi.security import OAuth2PasswordBearer
import jwt
import requests
from metrics import metr_endpoint, api_metr
from tracing import setup_tracing
from trace_dec import trace_function


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
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid token")


async def lifespan(app: FastAPI) -> AsyncGenerator:
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)

tracer = setup_tracing(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/metr")
@trace_function(name="get_metr", include_request=True)
async def metr():
    return await metr_endpoint()

@app.get("/cart/add")
@api_metr()
@trace_function(name="add_to_cart", include_request=True)
async def add_to_cart(product_id: int = None, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    user_id = verify_token(token)
    cart = await add_product_to_cart(db, user_id, product_id)
    print("DEBUG CART SERVICE add_to_cart, user_id:", user_id, "token:", token)
    print("DEBUG CART SERVICE add_to_cart, cart:", cart)
    # Здесь логика добавления товара в корзину для user_id
    if cart:
        return {"success": True, "message": "Product added to cart"}
    else:
        raise HTTPException(status_code=500, detail="Failed to add product to cart")


@app.get("/check_cart")
@api_metr()
@trace_function(name="check_cart", include_request=True)
async def check_cart(product_id: int = None, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    user_id = verify_token(token)  
    print("DEBUG CART SERVICE check_cart, user_id: ", user_id)
    cart = await get_cart_by_user_id(db, user_id)
    print("DEBUG CART SERVICE check_cart, cart: ", cart)
    if not cart:
        return {"exists": False}

    cart_item = await db.execute(
        select(CartItem).filter(
            CartItem.product_id == product_id,
            CartItem.cart_id == cart.id
        )
    )
    cart_item = cart_item.scalar_one_or_none()
    print("DEBUG CART SERVICE check_cart, cart_item: ", cart_item)

    if cart_item:
        return {"exists": True}
    return {"exists": False}


@app.get("/cart/delete")
@api_metr()
@trace_function(name="delete_from_cart", include_request=True)
async def delete_from_cart(product_id: int = None, token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    user_id = verify_token(token)
    cart = await remove_product_from_cart(db, user_id, product_id)
    print("DEBUG CART SERVICE delete_from_cart, user_id:", user_id, "token:", token)
    print("DEBUG CART SERVICE delete_from_cart, cart:", cart)
    if cart:
        return {"success": True, "message": "Product delete from cart"}
    else:
        raise HTTPException(status_code=500, detail="Failed to delete product from cart")




@app.get("/cart/createorder")
@api_metr()
@trace_function(name="create_order", include_request=True)
async def create_order(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        user_id = verify_token(token)
        cart_data = await get_cart_with_items(db, user_id)

        if not cart_data:
            return {"error": "Cart not found"}
        else:
            print("DEBUG CART SERVICE create_order, cart_data:", cart_data)

        headers = {
            "Auth": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        order_response = requests.post(
            "http://auth:8001/create_order",
            headers=headers,
            json=cart_data
        )
        if order_response.status_code != 200:
            raise HTTPException(status_code=502, detail="Order service error")

        order_id = order_response.json().get("order_id")

        if order_id:
            for item in cart_data["cart_items"]:
                try:
                    requests.post(
                        "http://catalog:8003/api/products/decrement_stock",
                        json={"product_id": item["product_id"], "quantity": item["quantity"]},
                        timeout=3
                    )
                except Exception as e:
                    print(f"Ошибка уменьшения stock для товара {item['product_id']}: {e}")
            await clear_user_cart(db, user_id)

        return {"message": "Order created successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cart/{user_id}")
@api_metr()
@trace_function(name="get_cart", include_request=True)
async def get_cart(user_id: int, db: AsyncSession = Depends(get_db)):
    items = await get_cart_items(db, user_id)
    print("DEBUG: cart items: ", items)
    return items

@app.post("/cart/{user_id}", response_model=CartResponse)
@api_metr()
@trace_function(name="add_to_cart_post", include_request=True)
async def add_to_cart(user_id: int, product: CartItemBase, db: AsyncSession = Depends(get_db)):
    cart = await add_product_to_cart(db, user_id, product.product_id, product.quantity)
    return cart

@app.put("/cart/{user_id}/{product_id}", response_model=CartResponse)
@api_metr()
@trace_function(name="update_cart_item_quantity", include_request=True)
async def update_cart_item_quantity(user_id: int, product_id: int, quantity: int, db: AsyncSession = Depends(get_db)):
    cart = await update_product_quantity_in_cart(db, user_id, product_id, quantity)
    return cart


@app.get("/")
@api_metr()
@trace_function(name="health_check", include_request=True)
async def health_check():
    """Health check endpoint."""
    return {"status": "cart running"}

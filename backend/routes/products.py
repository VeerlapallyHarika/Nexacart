from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from services.product_service import ProductService
from schemas.product import ProductResponse
from typing import List

router = APIRouter()


@router.get("/api/products", response_model=List[ProductResponse])
def get_products(db: Session = Depends(get_db)):
    return ProductService.get_products(db)


@router.get("/api/products/{product_id}", response_model=ProductResponse)
def get_product(product_id: str, db: Session = Depends(get_db)):
    product = ProductService.get_product(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

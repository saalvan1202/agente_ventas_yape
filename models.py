from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    price = Column(Float)
    
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    sale_details = relationship("SaleDetail", back_populates="product")

class ProductImage(Base):
    __tablename__ = "product_images"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    image_path = Column(String)
    is_main = Column(Boolean, default=False)
    
    product = relationship("Product", back_populates="images")

class Sale(Base):
    __tablename__ = "sales"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    total_amount = Column(Float)
    
    details = relationship("SaleDetail", back_populates="sale", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="sale")

class SaleDetail(Base):
    __tablename__ = "sale_details"
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    unit_price = Column(Float)
    
    sale = relationship("Sale", back_populates="details")
    product = relationship("Product", back_populates="sale_details")

class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, index=True)
    sale_id = Column(Integer, ForeignKey("sales.id"))
    total_paid = Column(Float)
    
    sale = relationship("Sale", back_populates="payments")
    details = relationship("PaymentDetail", back_populates="payment", cascade="all, delete-orphan")

class PaymentDetail(Base):
    __tablename__ = "payment_details"
    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(Integer, ForeignKey("payments.id"))
    
    destino = Column(String)
    nombre = Column(String)
    fecha = Column(String)
    hora = Column(String)
    num_operacion = Column(String)
    cod_seguridad = Column(String)
    monto = Column(String) # Guardado como string segun el formato: "S/ 4.50"
    
    payment = relationship("Payment", back_populates="details")

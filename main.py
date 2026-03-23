import os
import uuid
from typing import List
from fastapi import FastAPI, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import engine, get_db, Base
import models

# Crear tablas en la base de datos
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Configurar archivos estáticos y plantillas
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Directorio de subida de imágenes
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    return templates.TemplateResponse("products.html", {"request": request, "products": products})

@app.get("/products/new", response_class=HTMLResponse)
async def new_product_form(request: Request):
    return templates.TemplateResponse("product_form.html", {"request": request})

@app.post("/products")
async def create_product(
    name: str = Form(...),
    price: float = Form(...),
    images: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    new_product = models.Product(name=name, price=price)
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    
    for image in images:
        if image.filename:
            file_ext = image.filename.split(".")[-1]
            file_name = f"{uuid.uuid4()}.{file_ext}"
            file_path = f"{UPLOAD_DIR}/{file_name}"
            with open(file_path, "wb") as f:
                f.write(await image.read())
            
            new_image = models.ProductImage(product_id=new_product.id, image_path=f"uploads/{file_name}")
            db.add(new_image)
    
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/sales", response_class=HTMLResponse)
async def list_sales(request: Request, db: Session = Depends(get_db)):
    sales = db.query(models.Sale).order_by(models.Sale.created_at.desc()).all()
    return templates.TemplateResponse("sales.html", {"request": request, "sales": sales})

@app.get("/sales/new", response_class=HTMLResponse)
async def new_sale_form(request: Request, db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    return templates.TemplateResponse("sale_form.html", {"request": request, "products": products})

@app.post("/sales")
async def create_sale(
    product_ids: List[int] = Form(...),
    quantities: List[int] = Form(...),
    db: Session = Depends(get_db)
):
    total = 0
    sale_items = []
    
    for pid, qty in zip(product_ids, quantities):
        product = db.query(models.Product).filter(models.Product.id == pid).first()
        if product:
            total += product.price * qty
            sale_items.append((product, qty))
    
    new_sale = models.Sale(total_amount=total)
    db.add(new_sale)
    db.commit()
    db.refresh(new_sale)
    
    for product, qty in sale_items:
        detail = models.SaleDetail(
            sale_id=new_sale.id,
            product_id=product.id,
            quantity=qty,
            unit_price=product.price
        )
        db.add(detail)
    
    db.commit()
    return RedirectResponse(url=f"/sales/{new_sale.id}", status_code=303)

@app.get("/sales/{sale_id}/payment", response_class=HTMLResponse)
async def payment_form(sale_id: int, request: Request, db: Session = Depends(get_db)):
    sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
        
    # Calcular balance
    total_paid = sum(p.total_paid for p in sale.payments)
    balance = sale.total_amount - total_paid
    
    return templates.TemplateResponse("payment_form.html", {
        "request": request, 
        "sale": sale, 
        "balance": balance
    })

@app.post("/payments")
async def record_payment(
    sale_id: int = Form(...),
    destino: str = Form(...),
    nombre: str = Form(...),
    fecha: str = Form(...),
    hora: str = Form(...),
    num_operacion: str = Form(...),
    cod_seguridad: str = Form(...),
    monto: str = Form(...),
    db: Session = Depends(get_db)
):
    sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    
    # Extraer el monto numérico de "S/ 123.00" o similar
    try:
        monto_float = float(monto.replace("S/ ", "").replace(",", "").strip())
    except ValueError:
        monto_float = 0.0
        
    new_payment = models.Payment(sale_id=sale.id, total_paid=monto_float)
    db.add(new_payment)
    db.commit()
    db.refresh(new_payment)
    
    payment_detail = models.PaymentDetail(
        payment_id=new_payment.id,
        destino=destino,
        nombre=nombre,
        fecha=fecha,
        hora=hora,
        num_operacion=num_operacion,
        cod_seguridad=cod_seguridad,
        monto=monto
    )
    db.add(payment_detail)
    db.commit()
    
    return RedirectResponse(url=f"/sales/{sale.id}", status_code=303)

@app.get("/products/{product_id}/main-image")
async def get_main_image(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product or not product.images:
        raise HTTPException(status_code=404, detail="Image not found")
    
    image_path = f"static/{product.images[0].image_path}"
    if os.path.exists(image_path):
        from fastapi.responses import FileResponse
        return FileResponse(image_path)
    
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/products/share-all")
async def share_all_products_wsp(number: str, db: Session = Depends(get_db)):
    import requests
    import base64
    products = db.query(models.Product).all()
    if not products:
        raise HTTPException(status_code=404, detail="No products found")
    
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzODU3MyIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6ImNvbnN1bHRvciJ9.dKmKFEJ438eSF6gx4L52asNttTiVEbBd9RMxYj3GyE0"
    instance_name = os.getenv("WSP_INSTANCE", "default-instance")
    url = f"https://apiwsp.factiliza.com/v1/message/sendmedia/{instance_name}"
    
    responses = []
    for product in products:
        if not product.images:
            print("sin imagen", product.name)
            continue
            
        image_path = f"static/{product.images[0].image_path}"
        if not os.path.exists(image_path):
            print("no existe la imagen", image_path)
            continue
            
        with open(image_path, "rb") as img_file:
            b64_string = base64.b64encode(img_file.read()).decode('utf-8')
            
        caption = f"Código del producto: {product.id}\n🛍️ *{product.name}*\n💰 Precio: S/ {product.price:.2f}"
        
        payload = {
            "number": number,
            "mediatype": "image",
            "media": b64_string,
            "filename": f"{product.name}.jpg",
            "caption": caption
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        try:
            res = requests.post(url, json=payload, headers=headers)
            responses.append({"product": product.name, "response": res.json()})
        except Exception as e:
            responses.append({"product": product.name, "error": str(e)})
            
    return {"status": "completed", "results": responses}

@app.get("/products/{product_id}/share")
async def share_product_wsp(product_id: int, number: str, request: Request, db: Session = Depends(get_db)):
    import requests
    import base64
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product or not product.images:
        raise HTTPException(status_code=404, detail="Product or images not found")
    
    # Leer imagen local y convertir a Base64
    image_path = f"static/{product.images[0].image_path}"
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image file not found")
    
    with open(image_path, "rb") as img_file:
        b64_string = base64.b64encode(img_file.read()).decode('utf-8')
    
    # Configuración de WSP (Factiliza)
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzODU3MyIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6ImNvbnN1bHRvciJ9.dKmKFEJ438eSF6gx4L52asNttTiVEbBd9RMxYj3GyE0"
    instance_name = os.getenv("WSP_INSTANCE", "default-instance")
    url = f"https://apiwsp.factiliza.com/v1/message/sendmedia/{instance_name}"
    
    caption = f"🛍️ *{product.name}*\n💰 Precio: S/ {product.price:.2f}\n\n¡Consulta por este producto ahora mismo! 🚀"
    
    payload = {
        "number": number,
        "mediatype": "image",
        "media": b64_string,
        "filename": f"{product.name}.jpg",
        "caption": caption
    }
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        return {"status": "success", "wsp_response": response.json()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/products")
async def api_get_products(request: Request, db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    base_url = str(request.base_url).rstrip('/')
    result = []
    for p in products:
        result.append({
            "id": p.id,
            "name": p.name,
            "price": p.price,
            "images": [f"{base_url}/static/{img.image_path}" for img in p.images]
        })
    return result

@app.get("/sales/{sale_id}", response_class=HTMLResponse)
async def sale_detail_view(sale_id: int, request: Request, db: Session = Depends(get_db)):
    sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return templates.TemplateResponse("sale_detail.html", {"request": request, "sale": sale})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

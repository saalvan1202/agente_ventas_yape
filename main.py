import os
import uuid
from typing import List
from fastapi import FastAPI, Depends, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
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

# Actualizar esquema (Añade campo is_main si no existe)
def update_schema():
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            # PostgreSQL syntax
            conn.execute(text("ALTER TABLE product_images ADD COLUMN IF NOT EXISTS is_main BOOLEAN DEFAULT FALSE"))
            conn.commit()
        except Exception as e:
            print(f"Schema update skipped or failed: {e}")

update_schema()

# Modelos para validación de datos (Pydantic)
class SaleItemSchema(BaseModel):
    product_id: int
    quantity: int

class SaleCreateSchema(BaseModel):
    items: List[SaleItemSchema]

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
@app.get("/products/share-gallery")
async def share_product_gallery_wsp(product_id: int, number: str, db: Session = Depends(get_db)):
    import requests
    import base64
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product or not product.images:
        raise HTTPException(status_code=404, detail="Product or images not found")
    
    # Filtrar solo imágenes que NO son principales
    gallery_images = [img for img in product.images if not img.is_main]
    
    if not gallery_images:
        return {"status": "info", "message": "El producto no tiene imágenes adicionales en la galería"}

    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzODU3MyIsImh0dHA6Ly9zY2hlbWFzLm1pY3Jvc29mdC5jb20vd3MvMjAwOC8wNi9pZGVudGl0eS9jbGFpbXMvcm9sZSI6ImNvbnN1bHRvciJ9.dKmKFEJ438eSF6gx4L52asNttTiVEbBd9RMxYj3GyE0"
    instance_name = os.getenv("WSP_INSTANCE", "default-instance")
    url = f"https://apiwsp.factiliza.com/v1/message/sendmedia/{instance_name}"
    
    sent_count = 0
    for img in gallery_images:
        image_path = f"static/{img.image_path}"
        if os.path.exists(image_path):
            with open(image_path, "rb") as image_file:
                b64_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            payload = {
                "number": number,
                "mediatype": "image",
                "media": b64_string,
                "filename": f"{product.name}_gal_{sent_count+1}.jpg",
                "caption": f"🖼️ Galería de {product.name} ({sent_count+1}/{len(gallery_images)})"
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            
            try:
                requests.post(url, json=payload, headers=headers)
                sent_count += 1
            except:
                pass
                
    return {"status": "success", "message": f"Se enviaron {sent_count} imágenes de la galería"}

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

@app.get("/sales/new", response_class=HTMLResponse)
async def new_sale_form(request: Request, db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    return templates.TemplateResponse(request, "sale_form.html", {"products": products})

@app.get("/sales/{sale_id}", response_class=HTMLResponse)
async def sale_detail_view(sale_id: int, request: Request, db: Session = Depends(get_db)):
    sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
    return templates.TemplateResponse(request, "sale_detail.html", {"sale": sale})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    return templates.TemplateResponse(request, "products.html", {"products": products})

@app.get("/products/new", response_class=HTMLResponse)
async def new_product_form(request: Request):
    return templates.TemplateResponse(request, "product_form.html")

@app.post("/products")
async def create_product(
    name: str = Form(...),
    price: float = Form(...),
    main_image: UploadFile = File(...),
    gallery_images: List[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    new_product = models.Product(name=name, price=price)
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    
    # Guardar imagen principal
    if main_image.filename:
        file_ext = main_image.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_ext}"
        file_path = f"{UPLOAD_DIR}/{file_name}"
        with open(file_path, "wb") as f:
            f.write(await main_image.read())
        
        new_image = models.ProductImage(product_id=new_product.id, image_path=f"uploads/{file_name}", is_main=True)
        db.add(new_image)
    
    # Guardar galería
    if gallery_images:
        for image in gallery_images:
            if image.filename:
                file_ext = image.filename.split(".")[-1]
                file_name = f"{uuid.uuid4()}.{file_ext}"
                file_path = f"{UPLOAD_DIR}/{file_name}"
                with open(file_path, "wb") as f:
                    f.write(await image.read())
                
                new_image = models.ProductImage(product_id=new_product.id, image_path=f"uploads/{file_name}", is_main=False)
                db.add(new_image)
    
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def edit_product_form(product_id: int, request: Request, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return templates.TemplateResponse(request, "product_form.html", {"product": product})

@app.get("/products/{product_id}", response_class=HTMLResponse)
async def product_detail_view(product_id: int, request: Request, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return templates.TemplateResponse(request, "product_detail.html", {"product": product})

@app.post("/products/{product_id}")
async def update_product(
    product_id: int,
    name: str = Form(...),
    price: float = Form(...),
    main_image: UploadFile = File(None),
    gallery_images: List[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product.name = name
    product.price = price
    
    # Manejar nueva imagen principal
    if main_image and main_image.filename:
        # Desactivar anterior principal
        for img in product.images:
            if img.is_main:
                img.is_main = False
        
        file_ext = main_image.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_ext}"
        file_path = f"{UPLOAD_DIR}/{file_name}"
        with open(file_path, "wb") as f:
            f.write(await main_image.read())
        
        new_main = models.ProductImage(product_id=product.id, image_path=f"uploads/{file_name}", is_main=True)
        db.add(new_main)
    
    # Manejar galería de imágenes adicional
    if gallery_images:
        for img_file in gallery_images:
            if img_file.filename:
                file_ext = img_file.filename.split(".")[-1]
                file_name = f"{uuid.uuid4()}.{file_ext}"
                file_path = f"{UPLOAD_DIR}/{file_name}"
                with open(file_path, "wb") as f:
                    f.write(await img_file.read())
                
                new_gallery = models.ProductImage(product_id=product.id, image_path=f"uploads/{file_name}", is_main=False)
                db.add(new_gallery)
    
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.delete("/products/images/{image_id}")
async def delete_product_image(image_id: int, db: Session = Depends(get_db)):
    img = db.query(models.ProductImage).filter(models.ProductImage.id == image_id).first()
    if not img:
        raise HTTPException(status_code=404, detail="Image not found")
    
    # Prevenir eliminar la única imagen principal si se desea
    # (Opcional, pero por ahora lo permitimos si el usuario elige otra)
    
    # Ruta física
    file_path = f"static/{img.image_path}"
    if os.path.exists(file_path):
        os.remove(file_path)
    
    db.delete(img)
    db.commit()
    return {"status": "success", "message": "Imagen eliminada"}

@app.get("/sales", response_class=HTMLResponse)
async def list_sales(
    request: Request, 
    start_date: str = None, 
    end_date: str = None,
    month: int = None,
    year: int = None,
    db: Session = Depends(get_db)
):
    from datetime import datetime
    now = datetime.now()
    
    # Establecer valores por defecto si no hay filtros manuales
    is_default = False
    if not any([start_date, end_date, month, year]):
        month = now.month
        year = now.year
        is_default = True
        
    query = db.query(models.Sale)
    
    if start_date:
        query = query.filter(models.Sale.created_at >= start_date)
    if end_date:
        query = query.filter(models.Sale.created_at <= end_date)
    if year:
        from sqlalchemy import extract
        query = query.filter(extract('year', models.Sale.created_at) == year)
    if month:
        from sqlalchemy import extract
        query = query.filter(extract('month', models.Sale.created_at) == month)
        
    sales = query.order_by(models.Sale.created_at.desc()).all()
    
    # Calcular totales para el resumen
    total_revenue = sum(s.total_amount for s in sales)
    order_count = len(sales)
    
    return templates.TemplateResponse(request, "sales.html", {
        "sales": sales,
        "total_revenue": total_revenue,
        "order_count": order_count,
        "filters": {
            "start_date": start_date,
            "end_date": end_date,
            "month": month,
            "year": year
        }
    })


@app.post("/sales")
async def create_sale(
    sale_data: SaleCreateSchema,
    db: Session = Depends(get_db)
):
    total = 0
    sale_items = []
    
    for item in sale_data.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).first()
        if product:
            total += product.price * item.quantity
            sale_items.append((product, item.quantity))
    
    if not sale_items:
        raise HTTPException(status_code=400, detail="No valid products in sale")
        
    new_sale = models.Sale(total_amount=total)
    db.add(new_sale)
    db.commit()
    db.refresh(new_sale)
    
    details_for_webhook = []
    for product, qty in sale_items:
        detail = models.SaleDetail(
            sale_id=new_sale.id,
            product_id=product.id,
            quantity=qty,
            unit_price=product.price
        )
        db.add(detail)
        details_for_webhook.append({
            "product": product.name,
            "quantity": qty,
            "price": product.price
        })
    
    db.commit()

    # Integración con n8n (Opcional)
    n8n_webhook = os.getenv("N8N_WEBHOOK_URL")
    if n8n_webhook:
        import requests
        try:
            requests.post(n8n_webhook, json={
                "event": "sale_created",
                "sale_id": new_sale.id,
                "total": total,
                "items": details_for_webhook
            })
        except:
            pass # No bloquear si falla n8n
            
    return {"status": "success", "sale_id": new_sale.id, "redirect_url": f"/sales/{new_sale.id}"}

@app.get("/sales/{sale_id}/payment", response_class=HTMLResponse)
async def payment_form(sale_id: int, request: Request, db: Session = Depends(get_db)):
    sale = db.query(models.Sale).filter(models.Sale.id == sale_id).first()
    if not sale:
        raise HTTPException(status_code=404, detail="Sale not found")
        
    # Calcular balance
    total_paid = sum(p.total_paid for p in sale.payments)
    balance = sale.total_amount - total_paid
    
    return templates.TemplateResponse(request, "payment_form.html", {
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
    
    # Buscar imagen principal
    main_img = next((img for img in product.images if img.is_main), product.images[0])
    
    image_path = f"static/{main_img.image_path}"
    if os.path.exists(image_path):
        from fastapi.responses import FileResponse
        return FileResponse(image_path)
    
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/products/{product_id}/share")
async def share_product_wsp(product_id: int, number: str, request: Request, db: Session = Depends(get_db)):
    import requests
    import base64
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product or not product.images:
        raise HTTPException(status_code=404, detail="Product or images not found")
    
    # Leer imagen local y convertir a Base64
    main_img = next((img for img in product.images if img.is_main), product.images[0])
    image_path = f"static/{main_img.image_path}"
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



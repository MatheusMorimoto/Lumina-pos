"""API pública v1 do PDV. Mantém os nomes do contrato de integração."""
from __future__ import annotations

import csv
import hashlib
import io
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from supabase import Client

from app.core.database import get_supabase_client, unwrap_response
from app.shared.exceptions import BusinessRuleError, ConflictError, NotFoundError

router = APIRouter(tags=["POS API"])
Db = Annotated[Client, Depends(get_supabase_client)]


class ProductIn(BaseModel):
    store_id: UUID
    name: str = Field(min_length=2, max_length=200)
    sku: str = Field(min_length=1, max_length=80)
    barcode: str | None = None
    sale_price: Decimal = Field(ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)
    active: bool = True


class ProductPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    sku: str | None = None
    barcode: str | None = None
    sale_price: Decimal | None = Field(default=None, ge=0)
    tax_amount: Decimal | None = Field(default=None, ge=0)
    active: bool | None = None


class BatchIn(BaseModel):
    lot_number: str
    expires_at: date | None = None
    purchase_price: Decimal = Field(default=Decimal("0"), ge=0)
    quantity: Decimal = Field(ge=0)


class MovementIn(BaseModel):
    product_id: UUID
    batch_id: UUID | None = None
    type: str
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal | None = None
    reference_type: str | None = None
    reference_id: UUID | None = None
    notes: str | None = None


class PromotionIn(BaseModel):
    promotional_price: Decimal = Field(ge=0)
    starts_at: datetime
    ends_at: datetime
    active: bool = True


class SaleIn(BaseModel):
    store_id: UUID
    cash_session_id: UUID
    customer_id: UUID | None = None
    discount: Decimal = Field(default=Decimal("0"), ge=0)


class ItemIn(BaseModel):
    product_id: UUID
    batch_id: UUID | None = None
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount: Decimal = Field(default=Decimal("0"), ge=0)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0)


class PaymentIn(BaseModel):
    method: str
    amount: Decimal = Field(gt=0)
    institution_id: UUID | None = None
    installments: int = Field(default=1, gt=0)
    authorization_code: str | None = None
    due_date: date | None = None


class FinalizeIn(BaseModel):
    payments: list[PaymentIn] = Field(min_length=1)


class CustomerIn(BaseModel):
    store_id: UUID
    name: str
    document: str | None = None
    phone: str | None = None
    email: str | None = None
    credit_limit: Decimal = Field(default=Decimal("0"), ge=0)
    active: bool = True


class ReceivablePaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    payment_method: str
    user_id: UUID
    paid_at: datetime | None = None


class CashOpenIn(BaseModel):
    cash_register_id: UUID
    user_id: UUID
    opening_amount: Decimal = Field(default=Decimal("0"), ge=0)


class CashCloseIn(BaseModel):
    declared_amount: Decimal = Field(ge=0)


class DeliveryIn(BaseModel):
    sale_id: UUID
    customer_id: UUID | None = None
    courier_id: UUID | None = None
    address: dict[str, Any]
    scheduled_at: datetime | None = None


class StatusIn(BaseModel):
    status: str
    user_id: UUID


class CourierAssignIn(BaseModel):
    courier_id: UUID


def one(query: Any, message: str) -> dict[str, Any]:
    rows = unwrap_response(query.execute())
    if not rows:
        raise NotFoundError(message)
    return rows[0]


def insert(db: Client, table: str, model: BaseModel | dict[str, Any]) -> dict[str, Any]:
    payload = model.model_dump(mode="json", exclude_none=True) if isinstance(model, BaseModel) else model
    return one(db.table(table).insert(payload), f"Falha ao criar registro em {table}.")


@router.get("/products")
def products(db: Db, search: str | None = None, barcode: str | None = None) -> list[dict[str, Any]]:
    q = db.table("products").select("*")
    if barcode:
        q = q.eq("barcode", barcode)
    if search:
        safe = search.replace(",", "")
        q = q.or_(f"name.ilike.%{safe}%,sku.ilike.%{safe}%,barcode.ilike.%{safe}%")
    return unwrap_response(q.order("name").execute())


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(data: ProductIn, db: Db) -> dict[str, Any]: return insert(db, "products", data)


@router.get("/products/{product_id}")
def get_product(product_id: UUID, db: Db) -> dict[str, Any]:
    return one(db.table("products").select("*").eq("id", str(product_id)).limit(1), "Produto não encontrado.")


@router.patch("/products/{product_id}")
def patch_product(product_id: UUID, data: ProductPatch, db: Db) -> dict[str, Any]:
    payload = data.model_dump(mode="json", exclude_none=True)
    if not payload: return get_product(product_id, db)
    payload["updated_at"] = datetime.now().astimezone().isoformat()
    return one(db.table("products").update(payload).eq("id", str(product_id)), "Produto não encontrado.")


@router.get("/products/{product_id}/batches")
def batches(product_id: UUID, db: Db) -> list[dict[str, Any]]:
    return unwrap_response(db.table("inventory_batches").select("*").eq("product_id", str(product_id)).order("expires_at").execute())


@router.post("/products/{product_id}/batches", status_code=201)
def create_batch(product_id: UUID, data: BatchIn, db: Db) -> dict[str, Any]:
    payload = data.model_dump(mode="json"); payload["product_id"] = str(product_id)
    row = insert(db, "inventory_batches", payload)
    if data.quantity > 0:
        insert(db, "stock_movements", {"product_id": str(product_id), "batch_id": row["id"], "type": "in", "quantity": str(data.quantity), "unit_cost": str(data.purchase_price), "reference_type": "batch"})
    return row


@router.post("/stock/movements", status_code=201)
def movement(data: MovementIn, db: Db) -> dict[str, Any]:
    if data.type not in {"in", "out", "adjustment", "return"}: raise BusinessRuleError("Tipo de movimento inválido.")
    if data.batch_id:
        batch = one(db.table("inventory_batches").select("quantity").eq("id", str(data.batch_id)).limit(1), "Lote não encontrado.")
        current = Decimal(str(batch["quantity"])); delta = data.quantity if data.type in {"in", "return"} else -data.quantity
        if current + delta < 0: raise BusinessRuleError("Saldo insuficiente no lote.")
        db.table("inventory_batches").update({"quantity": str(current + delta)}).eq("id", str(data.batch_id)).execute()
    return insert(db, "stock_movements", data)


@router.get("/stock")
def stock(db: Db, validity: str | None = Query(default=None, pattern="^(expired|soon|ok)$")) -> list[dict[str, Any]]:
    q = db.table("inventory_batches").select("*,products(*)").gt("quantity", 0)
    today = date.today(); soon = date.fromordinal(today.toordinal() + 30)
    if validity == "expired": q = q.lt("expires_at", today.isoformat())
    elif validity == "soon": q = q.gte("expires_at", today.isoformat()).lte("expires_at", soon.isoformat())
    elif validity == "ok": q = q.or_(f"expires_at.is.null,expires_at.gt.{soon.isoformat()}")
    return unwrap_response(q.order("expires_at").execute())


@router.post("/products/{product_id}/promotions", status_code=201)
def promotion(product_id: UUID, data: PromotionIn, db: Db) -> dict[str, Any]:
    if data.ends_at <= data.starts_at: raise BusinessRuleError("O fim deve ser posterior ao início.")
    payload=data.model_dump(mode="json"); payload["product_id"]=str(product_id); return insert(db,"promotions",payload)


@router.patch("/promotions/{promotion_id}")
def patch_promotion(promotion_id: UUID, data: PromotionIn, db: Db) -> dict[str, Any]:
    return one(db.table("promotions").update(data.model_dump(mode="json")).eq("id",str(promotion_id)),"Promoção não encontrada.")


@router.post("/sales", status_code=201)
def create_sale(data: SaleIn, db: Db) -> dict[str, Any]: return insert(db,"sales",data)


@router.get("/sales")
def list_sales(db: Db, start: date|None=None, end: date|None=None, payment_method: str|None=None, sale_status: str|None=Query(None,alias="status")) -> list[dict[str,Any]]:
    q=db.table("sales").select("*,sale_payments(*)")
    if start:q=q.gte("created_at",start.isoformat())
    if end:q=q.lt("created_at",date.fromordinal(end.toordinal()+1).isoformat())
    if sale_status:q=q.eq("status",sale_status)
    rows=unwrap_response(q.order("created_at",desc=True).execute())
    return [r for r in rows if not payment_method or any(p.get("method")==payment_method for p in r.get("sale_payments",[]))]


@router.get("/sales/{sale_id}")
def get_sale(sale_id:UUID,db:Db)->dict[str,Any]:
    return one(db.table("sales").select("*,sale_items(*,products(*)),sale_payments(*)").eq("id",str(sale_id)).limit(1),"Venda não encontrada.")


@router.post("/sales/{sale_id}/items",status_code=201)
def add_item(sale_id:UUID,data:ItemIn,db:Db)->dict[str,Any]:
    sale=one(db.table("sales").select("status").eq("id",str(sale_id)).limit(1),"Venda não encontrada.")
    if sale["status"]!="open":raise BusinessRuleError("A venda não está aberta.")
    payload=data.model_dump(mode="json",exclude_none=True);payload["sale_id"]=str(sale_id);return insert(db,"sale_items",payload)


@router.patch("/sales/{sale_id}/items/{item_id}")
def patch_item(sale_id:UUID,item_id:UUID,data:ItemIn,db:Db)->dict[str,Any]:
    return one(db.table("sale_items").update(data.model_dump(mode="json",exclude_none=True)).eq("id",str(item_id)).eq("sale_id",str(sale_id)),"Item não encontrado.")


@router.delete("/sales/{sale_id}/items/{item_id}",status_code=204)
def delete_item(sale_id:UUID,item_id:UUID,db:Db)->None:
    db.table("sale_items").delete().eq("id",str(item_id)).eq("sale_id",str(sale_id)).execute()


@router.post("/sales/{sale_id}/finalize")
def finalize_sale(sale_id:UUID,data:FinalizeIn,db:Db,idempotency_key:Annotated[str|None,Header(alias="Idempotency-Key")]=None)->dict[str,Any]:
    if not idempotency_key:raise BusinessRuleError("O cabeçalho Idempotency-Key é obrigatório.")
    rows=unwrap_response(db.rpc("finalize_sale",{"p_sale_id":str(sale_id),"p_payments":data.model_dump(mode="json")["payments"],"p_idempotency_key":idempotency_key}).execute())
    if not rows:raise ConflictError("Não foi possível finalizar a venda.")
    return rows[0]


@router.post("/sales/{sale_id}/cancel")
def cancel_sale(sale_id:UUID,db:Db)->dict[str,Any]:
    sale=get_sale(sale_id,db)
    if sale["status"]=="cancelled":return sale
    if sale["status"]=="completed":raise BusinessRuleError("Cancelamento de venda concluída exige estorno de estoque.")
    return one(db.table("sales").update({"status":"cancelled","cancelled_at":datetime.now().astimezone().isoformat()}).eq("id",str(sale_id)),"Venda não encontrada.")


@router.get("/customers")
def customers(db:Db,search:str|None=None,credit_status:str|None=None)->list[dict[str,Any]]:
    q=db.table("customers").select("*")
    if search:q=q.or_(f"name.ilike.%{search.replace(',','')}%,document.ilike.%{search.replace(',','')}%")
    rows=unwrap_response(q.order("name").execute())
    if credit_status:
        for r in rows:
            rec=unwrap_response(db.table("receivables").select("open_amount,due_date").eq("customer_id",r["id"]).gt("open_amount",0).execute())
            r["credit_status"]="overdue" if any(x["due_date"]<date.today().isoformat() for x in rec) else ("open" if rec else "clear")
        rows=[r for r in rows if r["credit_status"]==credit_status]
    return rows


@router.post("/customers",status_code=201)
def create_customer(data:CustomerIn,db:Db)->dict[str,Any]:return insert(db,"customers",data)
@router.get("/customers/{customer_id}")
def get_customer(customer_id:UUID,db:Db)->dict[str,Any]:return one(db.table("customers").select("*").eq("id",str(customer_id)).limit(1),"Cliente não encontrado.")
@router.patch("/customers/{customer_id}")
def patch_customer(customer_id:UUID,data:CustomerIn,db:Db)->dict[str,Any]:return one(db.table("customers").update(data.model_dump(mode="json",exclude_none=True)).eq("id",str(customer_id)),"Cliente não encontrado.")
@router.get("/customers/{customer_id}/receivables")
def customer_receivables(customer_id:UUID,db:Db)->list[dict[str,Any]]:return unwrap_response(db.table("receivables").select("*,receivable_payments(*)").eq("customer_id",str(customer_id)).execute())
@router.get("/receivables")
def receivables(db:Db,receivable_status:str|None=Query(None,alias="status"))->list[dict[str,Any]]:
    q=db.table("receivables").select("*,customers(*)")
    if receivable_status=="overdue":q=q.gt("open_amount",0).lt("due_date",date.today().isoformat())
    elif receivable_status:q=q.eq("status",receivable_status)
    return unwrap_response(q.order("due_date").execute())
@router.post("/receivables/{receivable_id}/payments",status_code=201)
def pay(receivable_id:UUID,data:ReceivablePaymentIn,db:Db)->dict[str,Any]:
    rows=unwrap_response(db.rpc("pay_receivable",{"p_receivable_id":str(receivable_id),"p_amount":str(data.amount),"p_method":data.payment_method,"p_user_id":str(data.user_id),"p_paid_at":data.paid_at.isoformat() if data.paid_at else datetime.now().astimezone().isoformat()}).execute())
    if not rows:raise NotFoundError("Conta a receber não encontrada.")
    return rows[0]


@router.post("/cash-sessions/open",status_code=201)
def open_cash(data:CashOpenIn,db:Db)->dict[str,Any]:return insert(db,"cash_sessions",data)
@router.get("/cash-sessions/current")
def current_cash(db:Db,cash_register_id:UUID|None=None,user_id:UUID|None=None)->dict[str,Any]:
    q=db.table("cash_sessions").select("*").eq("status","open")
    if cash_register_id:q=q.eq("cash_register_id",str(cash_register_id))
    if user_id:q=q.eq("user_id",str(user_id))
    return one(q.limit(1),"Não há sessão de caixa aberta.")
@router.post("/cash-sessions/{session_id}/close")
def close_cash(session_id:UUID,data:CashCloseIn,db:Db)->dict[str,Any]:
    s=one(db.table("cash_sessions").select("*").eq("id",str(session_id)).limit(1),"Sessão não encontrada.")
    if s["status"]!="open":raise BusinessRuleError("O caixa já está fechado.")
    pays=unwrap_response(db.table("sale_payments").select("amount,sales!inner(cash_session_id,status)").eq("sales.cash_session_id",str(session_id)).eq("sales.status","completed").execute())
    expected=Decimal(str(s["opening_amount"]))+sum((Decimal(str(p["amount"])) for p in pays),Decimal("0"))
    payload={"status":"closed","closed_at":datetime.now().astimezone().isoformat(),"declared_amount":str(data.declared_amount),"expected_amount":str(expected),"difference":str(data.declared_amount-expected)}
    return one(db.table("cash_sessions").update(payload).eq("id",str(session_id)),"Sessão não encontrada.")


def report_sales(db:Client,start:date,end:date)->list[dict[str,Any]]:
    return unwrap_response(db.table("sales").select("*,sale_payments(*)").eq("status","completed").gte("sold_at",start.isoformat()).lt("sold_at",date.fromordinal(end.toordinal()+1).isoformat()).execute())
@router.get("/reports/dashboard")
def dashboard(db:Db,report_date:date=Query(default_factory=date.today,alias="date"))->dict[str,Any]:
    rows=report_sales(db,report_date,report_date);total=sum((Decimal(str(x["total"])) for x in rows),Decimal("0"))
    return {"date":report_date,"sales_count":len(rows),"gross_sales":total,"average_ticket":total/len(rows) if rows else Decimal("0"),"payments":{m:sum((Decimal(str(p["amount"])) for s in rows for p in s.get("sale_payments",[]) if p["method"]==m),Decimal("0")) for m in {p["method"] for s in rows for p in s.get("sale_payments",[])}}}
@router.get("/reports/closures")
def closures(db:Db,start:date,end:date,group_by:str="day")->list[dict[str,Any]]:
    if group_by not in {"day","week","month","year"}:raise BusinessRuleError("Agrupamento inválido.")
    rows=report_sales(db,start,end); groups:dict[str,Decimal]={}
    for x in rows:
        d=datetime.fromisoformat(x["sold_at"].replace("Z","+00:00")); key=d.strftime({"day":"%Y-%m-%d","week":"%G-W%V","month":"%Y-%m","year":"%Y"}[group_by]);groups[key]=groups.get(key,Decimal("0"))+Decimal(str(x["total"]))
    return [{"period":k,"total":v} for k,v in sorted(groups.items())]
@router.get("/reports/dre")
def dre(db:Db,start:date,end:date)->dict[str,Any]:
    rows=report_sales(db,start,end);revenue=sum((Decimal(str(x["total"])) for x in rows),Decimal("0"));fees=sum((Decimal(str(p["amount"])) for x in rows for p in x.get("sale_payments",[]) if p.get("status")=="fee"),Decimal("0"))
    return {"start":start,"end":end,"gross_revenue":revenue,"discounts":sum((Decimal(str(x["discount"])) for x in rows),Decimal("0")),"fees":fees,"net_result":revenue-fees}
@router.get("/reports/closures/export")
def export_closures(db:Db,start:date,end:date,format:str="csv"):
    rows=report_sales(db,start,end)
    if format=="pdf":
        # PDF textual mínimo e válido, sem dependência nativa; adequado ao relatório tabular.
        lines=[f"Fechamentos {start} a {end}"]+[f"{x['sold_at']}  R$ {x['total']}" for x in rows]
        escaped="\\n".join(lines).replace("(","\\(").replace(")","\\)")
        stream=f"BT /F1 10 Tf 40 800 Td ({escaped}) Tj ET".encode("latin-1","replace")
        objects=[b"<< /Type /Catalog /Pages 2 0 R >>",b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",f"<< /Length {len(stream)} >>\nstream\n".encode()+stream+b"\nendstream",b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
        pdf=bytearray(b"%PDF-1.4\n");offsets=[]
        for i,obj in enumerate(objects,1):offsets.append(len(pdf));pdf.extend(f"{i} 0 obj\n".encode()+obj+b"\nendobj\n")
        xref=len(pdf);pdf.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode());[pdf.extend(f"{o:010} 00000 n \n".encode()) for o in offsets];pdf.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
        return Response(bytes(pdf),media_type="application/pdf",headers={"Content-Disposition":"attachment; filename=closures.pdf"})
    if format!="csv":raise BusinessRuleError("Formato inválido. Use PDF ou CSV.")
    output=io.StringIO();w=csv.writer(output);w.writerow(["id","sold_at","total","status"]);[w.writerow([x["id"],x["sold_at"],x["total"],x["status"]]) for x in rows]
    return StreamingResponse(iter([output.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=closures.csv"})


@router.get("/deliveries")
def deliveries(db:Db,delivery_status:str|None=Query(None,alias="status"))->list[dict[str,Any]]:
    q=db.table("deliveries").select("*,customers(*),couriers(*)");q=q.eq("status",delivery_status) if delivery_status else q;return unwrap_response(q.execute())
@router.post("/deliveries",status_code=201)
def create_delivery(data:DeliveryIn,db:Db)->dict[str,Any]:return insert(db,"deliveries",data)
@router.get("/deliveries/{delivery_id}")
def get_delivery(delivery_id:UUID,db:Db)->dict[str,Any]:return one(db.table("deliveries").select("*,delivery_status_history(*)").eq("id",str(delivery_id)).limit(1),"Entrega não encontrada.")
@router.patch("/deliveries/{delivery_id}")
def patch_delivery(delivery_id:UUID,data:DeliveryIn,db:Db)->dict[str,Any]:return one(db.table("deliveries").update(data.model_dump(mode="json",exclude_none=True)).eq("id",str(delivery_id)),"Entrega não encontrada.")
@router.post("/deliveries/{delivery_id}/status")
def delivery_status(delivery_id:UUID,data:StatusIn,db:Db)->dict[str,Any]:
    old=get_delivery(delivery_id,db);row=one(db.table("deliveries").update({"status":data.status,"delivered_at":datetime.now().astimezone().isoformat() if data.status=="delivered" else None}).eq("id",str(delivery_id)),"Entrega não encontrada.")
    insert(db,"delivery_status_history",{"delivery_id":str(delivery_id),"old_status":old["status"],"new_status":data.status,"user_id":str(data.user_id)});return row
@router.post("/deliveries/{delivery_id}/assign-courier")
def assign_courier(delivery_id:UUID,data:CourierAssignIn,db:Db)->dict[str,Any]:return one(db.table("deliveries").update({"courier_id":str(data.courier_id)}).eq("id",str(delivery_id)),"Entrega não encontrada.")


UPLOAD_DIR=Path("data/reconciliation")
@router.post("/reconciliation/imports",status_code=202)
async def reconciliation_import(db:Db,store_id:UUID,file:UploadFile=File(...))->dict[str,Any]:
    ext=Path(file.filename or "").suffix.lower();allowed={".csv",".ofx",".xlsx"}
    if ext not in allowed:raise BusinessRuleError("Formato não permitido. Use CSV, OFX ou XLSX.")
    content=await file.read(10*1024*1024+1)
    if len(content)>10*1024*1024:raise BusinessRuleError("Arquivo excede 10 MB.")
    digest=hashlib.sha256(content).hexdigest();existing=unwrap_response(db.table("reconciliation_imports").select("id").eq("file_hash",digest).limit(1).execute())
    if existing:raise ConflictError("Este arquivo já foi importado.")
    UPLOAD_DIR.mkdir(parents=True,exist_ok=True);path=UPLOAD_DIR/f"{digest}{ext}";path.write_bytes(content)
    return insert(db,"reconciliation_imports",{"store_id":str(store_id),"file_path":str(path),"format":ext[1:],"file_hash":digest,"file_size":len(content),"status":"pending"})
@router.get("/reconciliation/imports/{import_id}")
def get_import(import_id:UUID,db:Db)->dict[str,Any]:return one(db.table("reconciliation_imports").select("*").eq("id",str(import_id)).limit(1),"Importação não encontrada.")
@router.get("/reconciliation/transactions")
def transactions(db:Db)->list[dict[str,Any]]:return unwrap_response(db.table("acquirer_transactions").select("*").execute())
@router.post("/reconciliation/run",status_code=202)
def run_reconciliation()->dict[str,str]:return {"status":"queued"}
@router.get("/reconciliation/issues")
def issues(db:Db,issue_status:str|None=Query(None,alias="status"))->list[dict[str,Any]]:
    q=db.table("reconciliation_issues").select("*");q=q.eq("status",issue_status) if issue_status else q;return unwrap_response(q.execute())
@router.patch("/reconciliation/issues/{issue_id}")
def patch_issue(issue_id:UUID,payload:dict[str,Any],db:Db)->dict[str,Any]:return one(db.table("reconciliation_issues").update(payload).eq("id",str(issue_id)),"Pendência não encontrada.")
@router.get("/acquirer-fee-rules")
def fee_rules(db:Db)->list[dict[str,Any]]:return unwrap_response(db.table("acquirer_fee_rules").select("*").execute())
@router.post("/acquirer-fee-rules",status_code=201)
def create_fee_rule(payload:dict[str,Any],db:Db)->dict[str,Any]:return insert(db,"acquirer_fee_rules",payload)
@router.get("/acquirer-fee-rules/{rule_id}")
def get_fee_rule(rule_id:UUID,db:Db)->dict[str,Any]:return one(db.table("acquirer_fee_rules").select("*").eq("id",str(rule_id)).limit(1),"Regra não encontrada.")
@router.patch("/acquirer-fee-rules/{rule_id}")
def patch_fee_rule(rule_id:UUID,payload:dict[str,Any],db:Db)->dict[str,Any]:return one(db.table("acquirer_fee_rules").update(payload).eq("id",str(rule_id)),"Regra não encontrada.")
@router.delete("/acquirer-fee-rules/{rule_id}",status_code=204)
def delete_fee_rule(rule_id:UUID,db:Db)->None:db.table("acquirer_fee_rules").delete().eq("id",str(rule_id)).execute()

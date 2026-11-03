import streamlit as st
import sqlite3, pandas as pd, io, urllib.parse, os
from datetime import datetime
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("BILLING_DB_PATH", APP_DIR / "billing_data.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def conn():
    c=sqlite3.connect(DB_PATH, check_same_thread=False)
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS products(
          id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, sku TEXT DEFAULT '',
          price REAL NOT NULL DEFAULT 0, stock INTEGER NOT NULL DEFAULT 0, gst REAL NOT NULL DEFAULT 18);
        CREATE TABLE IF NOT EXISTS customers(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS bills(
          id INTEGER PRIMARY KEY, bill_no TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL,
          customer_name TEXT NOT NULL, phone TEXT DEFAULT '', subtotal REAL NOT NULL,
          gst_total REAL NOT NULL, grand_total REAL NOT NULL, items_json TEXT NOT NULL);
        """)
def dfq(query, params=()):
    with conn() as c: return pd.read_sql_query(query,c,params=params)
def run(query, params=()):
    with conn() as c: c.execute(query,params); c.commit()
def money(v): return f"₹{float(v):,.2f}"

st.set_page_config(page_title="Shop Billing Machine", page_icon="🧾", layout="wide")
init_db()
st.title("🧾 Shop Billing Machine")
st.caption("Persistent browser-based billing • Stock saved in local database • Excel export • WhatsApp bill sharing")
pages=st.tabs(["Create Bill","Stock / Products","Bills & Excel Export"])

with pages[0]:
    products=dfq("SELECT id,name,sku,price,stock,gst FROM products ORDER BY name")
    if products.empty:
        st.info("Add products in the Stock / Products tab before creating a bill.")
    else:
        col1,col2=st.columns(2)
        customer=col1.text_input("Customer name", "Walk-in Customer")
        phone=col2.text_input("WhatsApp number (country code, digits only)", placeholder="e.g. 919876543210")
        if "cart" not in st.session_state: st.session_state.cart=[]
        with st.form("add_item"):
            pnames=products["name"].tolist()
            selected=st.selectbox("Product",pnames)
            prod=products[products.name==selected].iloc[0]
            a,b,c=st.columns(3)
            qty=a.number_input("Quantity",min_value=1,max_value=max(1,int(prod.stock)),value=1,step=1)
            price=b.number_input("Unit price (₹)",min_value=0.0,value=float(prod.price),step=1.0)
            gst=c.number_input("GST %",min_value=0.0,max_value=100.0,value=float(prod.gst),step=0.5)
            add=st.form_submit_button("Add to bill")
        if add:
            if qty>int(prod.stock): st.error("Not enough stock.")
            else:
                st.session_state.cart.append({"product_id":int(prod.id),"name":prod["name"],"qty":int(qty),"price":float(price),"gst":float(gst)})
                st.rerun()
        if st.session_state.cart:
            cart=pd.DataFrame(st.session_state.cart)
            cart["line_total"]=cart.qty*cart.price
            cart["gst_amount"]=cart.line_total*cart.gst/100
            st.subheader("Bill items")
            st.dataframe(cart[["name","qty","price","gst","line_total","gst_amount"]],use_container_width=True,hide_index=True)
            subtotal=float(cart.line_total.sum()); gst_total=float(cart.gst_amount.sum()); total=subtotal+gst_total
            x,y,z=st.columns(3); x.metric("Subtotal",money(subtotal)); y.metric("GST",money(gst_total)); z.metric("Grand total",money(total))
            if st.button("Remove all items"): st.session_state.cart=[]; st.rerun()
            if st.button("Save bill & reduce stock",type="primary"):
                # Recheck stock transactionally.
                items=st.session_state.cart.copy()
                bill_no="BILL-"+datetime.now().strftime("%Y%m%d-%H%M%S")
                created=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                import json
                try:
                    with conn() as c:
                        c.execute("BEGIN IMMEDIATE")
                        for item in items:
                            row=c.execute("SELECT stock FROM products WHERE id=?",(item["product_id"],)).fetchone()
                            if not row or row[0] < item["qty"]: raise ValueError(f"Insufficient stock for {item['name']}")
                        for item in items:
                            c.execute("UPDATE products SET stock=stock-? WHERE id=?",(item["qty"],item["product_id"]))
                        c.execute("INSERT INTO bills(bill_no,created_at,customer_name,phone,subtotal,gst_total,grand_total,items_json) VALUES(?,?,?,?,?,?,?,?)",
                                  (bill_no,created,customer,phone,subtotal,gst_total,total,json.dumps(items)))
                        c.commit()
                    st.session_state.last_bill={"bill_no":bill_no,"created":created,"customer":customer,"phone":phone,"items":items,"subtotal":subtotal,"gst":gst_total,"total":total}
                    st.session_state.cart=[]
                    st.success(f"Saved {bill_no}. Stock was deducted and saved persistently.")
                except Exception as e: st.error(str(e))
        if "last_bill" in st.session_state:
            b=st.session_state.last_bill
            bill_text=f"*{b['bill_no']}*\\nDate: {b['created']}\\nCustomer: {b['customer']}\\n\\n"
            for item in b["items"]: bill_text+=f"{item['name']} x {item['qty']} = ₹{item['qty']*item['price']:.2f}\\n"
            bill_text+=f"\\nSubtotal: ₹{b['subtotal']:.2f}\\nGST: ₹{b['gst']:.2f}\\n*TOTAL: ₹{b['total']:.2f}*\\nThank you for your purchase!"
            st.text_area("Bill message (editable)",bill_text,key="bill_msg")
            number=st.session_state.get("wa_phone",b["phone"])
            st.session_state.wa_phone=st.text_input("WhatsApp number to send bill to",value=number)
            wa_url="https://wa.me/"+''.join(ch for ch in st.session_state.wa_phone if ch.isdigit())+"?text="+urllib.parse.quote(st.session_state.bill_msg)
            st.link_button("Open WhatsApp with bill",wa_url)
            st.caption("WhatsApp opens with the message prefilled. Review and press Send in WhatsApp.")

with pages[1]:
    st.subheader("Add or update stock")
    with st.form("product_form",clear_on_submit=True):
        name=st.text_input("Product name")
        sku=st.text_input("SKU / model (optional)")
        p,q,r=st.columns(3)
        price=p.number_input("Selling price (₹)",min_value=0.0,value=0.0,step=100.0)
        stock=q.number_input("Stock quantity",min_value=0,value=0,step=1)
        gst=r.number_input("GST %",min_value=0.0,max_value=100.0,value=18.0,step=0.5)
        save=st.form_submit_button("Save product")
    if save:
        if not name.strip(): st.error("Enter a product name.")
        else:
            try:
                run("INSERT INTO products(name,sku,price,stock,gst) VALUES(?,?,?,?,?)",(name.strip(),sku.strip(),price,int(stock),gst))
                st.success("Product saved.")
            except sqlite3.IntegrityError:
                run("UPDATE products SET sku=?,price=?,stock=stock+?,gst=? WHERE name=?",(sku.strip(),price,int(stock),gst,name.strip()))
                st.success("Existing product updated; entered stock was added.")
    inv=dfq("SELECT id,name,sku,price,stock,gst FROM products ORDER BY name")
    if not inv.empty:
        st.dataframe(inv,use_container_width=True,hide_index=True)
        with st.expander("Edit existing product or stock"):
            ids=inv.id.tolist(); pid=st.selectbox("Choose product ID",ids,format_func=lambda i: f"{i} — {inv[inv.id==i].iloc[0]['name']}")
            row=inv[inv.id==pid].iloc[0]
            nn=st.text_input("Name",value=row["name"],key="editname")
            np=st.number_input("Price",min_value=0.0,value=float(row.price),key="editprice")
            ns=st.number_input("Set stock to",min_value=0,value=int(row.stock),key="editstock")
            ng=st.number_input("GST",min_value=0.0,max_value=100.0,value=float(row.gst),key="editgst")
            if st.button("Update selected product"):
                run("UPDATE products SET name=?,price=?,stock=?,gst=? WHERE id=?",(nn,np,int(ns),ng,int(pid))); st.success("Updated."); st.rerun()

with pages[2]:
    bills=dfq("SELECT bill_no,created_at,customer_name,phone,subtotal,gst_total,grand_total FROM bills ORDER BY id DESC")
    st.subheader("Saved bills")
    st.dataframe(bills,use_container_width=True,hide_index=True)
    inventory=dfq("SELECT name,sku,price,stock,gst FROM products ORDER BY name")
    with conn() as c: bill_items=pd.read_sql_query("SELECT bill_no,created_at,customer_name,phone,items_json,subtotal,gst_total,grand_total FROM bills ORDER BY id",c)
    def excel_bytes():
        buf=io.BytesIO()
        with pd.ExcelWriter(buf,engine="openpyxl") as writer:
            inventory.to_excel(writer,index=False,sheet_name="Stock")
            bills.to_excel(writer,index=False,sheet_name="Bills")
            if not bill_items.empty:
                import json
                rows=[]
                for _,bill in bill_items.iterrows():
                    for item in json.loads(bill.items_json):
                        rows.append({"Bill No":bill.bill_no,"Date":bill.created_at,"Customer":bill.customer_name,"Phone":bill.phone,
                                     "Product":item["name"],"Qty":item["qty"],"Unit Price":item["price"],"GST %":item["gst"],
                                     "Line Amount":item["qty"]*item["price"]})
                pd.DataFrame(rows).to_excel(writer,index=False,sheet_name="Bill Items")
        return buf.getvalue()
    st.download_button("Download Excel workbook",data=excel_bytes(),file_name="shop_billing_export.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("The app's source of truth is its persistent SQLite database. Excel is an export, so reopening the app does not reset stock or bills.")

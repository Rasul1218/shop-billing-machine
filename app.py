import streamlit as st
import pandas as pd
import io, json, os, urllib.parse
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

st.set_page_config(page_title="Shop Billing Machine", page_icon="🧾", layout="wide")

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

def get_conn():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is missing. Set it in your hosting provider's Environment Variables.")
    return psycopg2.connect(DATABASE_URL, sslmode="require")

def init_db():
    with get_conn() as c:
        with c.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
              id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL, sku TEXT DEFAULT '',
              price NUMERIC(12,2) NOT NULL DEFAULT 0, stock INTEGER NOT NULL DEFAULT 0,
              gst NUMERIC(5,2) NOT NULL DEFAULT 18
            );
            CREATE TABLE IF NOT EXISTS bills (
              id SERIAL PRIMARY KEY, bill_no TEXT UNIQUE NOT NULL, created_at TIMESTAMP NOT NULL,
              customer_name TEXT NOT NULL, phone TEXT DEFAULT '', subtotal NUMERIC(12,2) NOT NULL,
              gst_total NUMERIC(12,2) NOT NULL, grand_total NUMERIC(12,2) NOT NULL,
              items_json JSONB NOT NULL
            );
            """)
def query_df(sql, params=()):
    with get_conn() as c:
        return pd.read_sql_query(sql, c, params=params)
def money(v): return f"₹{float(v):,.2f}"

try:
    init_db()
except Exception as e:
    st.error("Database connection/setup failed.")
    st.code(str(e))
    st.info("Check that DATABASE_URL is set to your Supabase PostgreSQL connection string, including the password.")
    st.stop()

st.title("🧾 Shop Billing Machine")
st.caption("Browser billing • Persistent PostgreSQL storage • Excel export • WhatsApp bill sharing")
tab_bill, tab_stock, tab_export = st.tabs(["Create Bill", "Stock / Products", "Bills & Excel Export"])

with tab_bill:
    products = query_df("SELECT id,name,sku,price,stock,gst FROM products ORDER BY name")
    if products.empty:
        st.info("Add products in the Stock / Products tab before creating a bill.")
    else:
        c1,c2=st.columns(2)
        customer=c1.text_input("Customer name", "Walk-in Customer")
        phone=c2.text_input("WhatsApp number (country code, digits only)", placeholder="e.g. 919876543210")
        if "cart" not in st.session_state: st.session_state.cart=[]
        with st.form("add_item"):
            selected=st.selectbox("Product", products["name"].tolist())
            prod=products[products.name==selected].iloc[0]
            a,b,c=st.columns(3)
            max_qty=max(1,int(prod.stock))
            qty=a.number_input("Quantity",min_value=1,max_value=max_qty,value=1,step=1)
            price=b.number_input("Unit price (₹)",min_value=0.0,value=float(prod.price),step=1.0)
            gst=c.number_input("GST %",min_value=0.0,max_value=100.0,value=float(prod.gst),step=0.5)
            add=st.form_submit_button("Add to bill")
        if add:
            if int(prod.stock)<int(qty): st.error("Not enough stock.")
            else:
                st.session_state.cart.append({"product_id":int(prod.id),"name":str(prod["name"]),"qty":int(qty),"price":float(price),"gst":float(gst)})
                st.rerun()
        if st.session_state.cart:
            cart=pd.DataFrame(st.session_state.cart)
            cart["line_total"]=cart.qty*cart.price
            cart["gst_amount"]=cart.line_total*cart.gst/100
            st.dataframe(cart[["name","qty","price","gst","line_total","gst_amount"]],use_container_width=True,hide_index=True)
            subtotal=float(cart.line_total.sum()); gst_total=float(cart.gst_amount.sum()); total=subtotal+gst_total
            x,y,z=st.columns(3); x.metric("Subtotal",money(subtotal)); y.metric("GST",money(gst_total)); z.metric("Grand total",money(total))
            if st.button("Clear cart"): st.session_state.cart=[]; st.rerun()
            if st.button("Save bill & reduce stock",type="primary"):
                items=st.session_state.cart.copy()
                bill_no="BILL-"+datetime.now().strftime("%Y%m%d-%H%M%S-%f")
                created=datetime.now()
                try:
                    with get_conn() as c:
                        with c.cursor() as cur:
                            # Lock/check stock and make the bill + inventory deduction one transaction.
                            for item in items:
                                cur.execute("SELECT stock FROM products WHERE id=%s FOR UPDATE",(item["product_id"],))
                                row=cur.fetchone()
                                if not row or row[0] < item["qty"]:
                                    raise ValueError(f"Insufficient stock for {item['name']}")
                            for item in items:
                                cur.execute("UPDATE products SET stock=stock-%s WHERE id=%s",(item["qty"],item["product_id"]))
                            cur.execute("""INSERT INTO bills(bill_no,created_at,customer_name,phone,subtotal,gst_total,grand_total,items_json)
                                           VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                                        (bill_no,created,customer,phone,subtotal,gst_total,total,json.dumps(items)))
                    st.session_state.last_bill={"bill_no":bill_no,"created":created.strftime("%Y-%m-%d %H:%M:%S"),
                        "customer":customer,"phone":phone,"items":items,"subtotal":subtotal,"gst":gst_total,"total":total}
                    st.session_state.cart=[]
                    st.success(f"Saved {bill_no}. Stock was deducted and saved.")
                except Exception as e: st.error(str(e))
        if "last_bill" in st.session_state:
            b=st.session_state.last_bill
            bill_text=f"*{b['bill_no']}*\\nDate: {b['created']}\\nCustomer: {b['customer']}\\n\\n"
            for item in b["items"]: bill_text+=f"{item['name']} x {item['qty']} = ₹{item['qty']*item['price']:.2f}\\n"
            bill_text+=f"\\nSubtotal: ₹{b['subtotal']:.2f}\\nGST: ₹{b['gst']:.2f}\\n*TOTAL: ₹{b['total']:.2f}*\\nThank you for your purchase!"
            st.text_area("Bill message (editable)",bill_text,key="bill_msg")
            wa_phone=st.text_input("WhatsApp number",value=b["phone"],key="wa_phone")
            wa_url="https://wa.me/"+''.join(ch for ch in wa_phone if ch.isdigit())+"?text="+urllib.parse.quote(st.session_state.bill_msg)
            st.link_button("Open WhatsApp with bill",wa_url)
            st.caption("WhatsApp opens with the message prefilled. Review and press Send in WhatsApp.")

with tab_stock:
    st.subheader("Add or update stock")
    with st.form("product_form",clear_on_submit=True):
        name=st.text_input("Product name")
        sku=st.text_input("SKU / model (optional)")
        a,b,c=st.columns(3)
        price=a.number_input("Selling price (₹)",min_value=0.0,value=0.0,step=100.0)
        stock=b.number_input("Stock quantity",min_value=0,value=0,step=1)
        gst=c.number_input("GST %",min_value=0.0,max_value=100.0,value=18.0,step=0.5)
        save=st.form_submit_button("Save product")
    if save:
        if not name.strip(): st.error("Enter a product name.")
        else:
            with get_conn() as c:
                with c.cursor() as cur:
                    cur.execute("""INSERT INTO products(name,sku,price,stock,gst) VALUES(%s,%s,%s,%s,%s)
                        ON CONFLICT(name) DO UPDATE SET sku=EXCLUDED.sku, price=EXCLUDED.price,
                        stock=products.stock+EXCLUDED.stock, gst=EXCLUDED.gst""",
                        (name.strip(),sku.strip(),price,int(stock),gst))
            st.success("Product saved. If it existed, entered stock was added.")
    inventory=query_df("SELECT id,name,sku,price,stock,gst FROM products ORDER BY name")
    if not inventory.empty:
        st.dataframe(inventory,use_container_width=True,hide_index=True)
        with st.expander("Edit existing product or stock"):
            pid=st.selectbox("Choose product",inventory.id.tolist(),format_func=lambda i:f"{i} — {inventory[inventory.id==i].iloc[0]['name']}")
            row=inventory[inventory.id==pid].iloc[0]
            nn=st.text_input("Name",value=str(row["name"]),key="editname")
            np=st.number_input("Price",min_value=0.0,value=float(row.price),key="editprice")
            ns=st.number_input("Set stock to",min_value=0,value=int(row.stock),key="editstock")
            ng=st.number_input("GST",min_value=0.0,max_value=100.0,value=float(row.gst),key="editgst")
            if st.button("Update selected product"):
                with get_conn() as c:
                    with c.cursor() as cur:
                        cur.execute("UPDATE products SET name=%s,price=%s,stock=%s,gst=%s WHERE id=%s",(nn,np,int(ns),ng,int(pid)))
                st.success("Updated."); st.rerun()

with tab_export:
    bills=query_df("SELECT bill_no,created_at,customer_name,phone,subtotal,gst_total,grand_total FROM bills ORDER BY id DESC")
    st.subheader("Saved bills")
    st.dataframe(bills,use_container_width=True,hide_index=True)
    inventory=query_df("SELECT name,sku,price,stock,gst FROM products ORDER BY name")
    items_df=query_df("SELECT bill_no,created_at,customer_name,phone,items_json,subtotal,gst_total,grand_total FROM bills ORDER BY id")
    def make_excel():
        buf=io.BytesIO()
        with pd.ExcelWriter(buf,engine="openpyxl") as writer:
            inventory.to_excel(writer,index=False,sheet_name="Stock")
            bills.to_excel(writer,index=False,sheet_name="Bills")
            rows=[]
            for _,bill in items_df.iterrows():
                details=bill["items_json"]
                if isinstance(details,str): details=json.loads(details)
                for item in details:
                    rows.append({"Bill No":bill.bill_no,"Date":bill.created_at,"Customer":bill.customer_name,"Phone":bill.phone,
                        "Product":item["name"],"Qty":item["qty"],"Unit Price":item["price"],"GST %":item["gst"],
                        "Line Amount":item["qty"]*item["price"]})
            pd.DataFrame(rows).to_excel(writer,index=False,sheet_name="Bill Items")
        return buf.getvalue()
    st.download_button("Download Excel workbook",data=make_excel(),file_name="shop_billing_export.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.caption("PostgreSQL is the permanent data source. Excel is an export/backup.")

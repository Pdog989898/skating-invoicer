import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
import os
from datetime import date, datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
import json
import urllib.request
import traceback

DB_PATH = 'skating.db'
INVOICE_DIR = 'invoices'
UPDATE_SETTINGS_FILE = 'update_settings.json'
os.makedirs(INVOICE_DIR, exist_ok=True)

ADMIN_USERNAME = "Patrick Carle"
ADMIN_PASSWORD = "95753578@Pc"

# ---------- Database ----------
def init_db():
    """Create DB and tables if needed. If skaters exists but missing 'paid' column, add it."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # skaters includes paid flag (0 or 1)
    c.execute('''CREATE TABLE IF NOT EXISTS skaters (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    paid INTEGER DEFAULT 0
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS lesson_types (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    rate REAL NOT NULL
                 )''')
    c.execute('''CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY,
                    skater_id INTEGER NOT NULL,
                    date TEXT NOT NULL,
                    amount REAL NOT NULL,
                    lesson_type_id INTEGER NOT NULL,
                    FOREIGN KEY(skater_id) REFERENCES skaters(id),
                    FOREIGN KEY(lesson_type_id) REFERENCES lesson_types(id)
                 )''')
    conn.commit()
    # In case an older DB lacks the 'paid' column, try to add it (safe)
    try:
        c.execute("PRAGMA table_info(skaters)")
        cols = [r[1] for r in c.fetchall()]
        if 'paid' not in cols:
            c.execute("ALTER TABLE skaters ADD COLUMN paid INTEGER DEFAULT 0")
            conn.commit()
    except Exception:
        pass
    conn.close()

def run_query(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(query, params)
    if fetch:
        rows = c.fetchall()
        conn.close()
        return rows
    conn.commit()
    conn.close()

# ---------- PDF Invoice ----------
def generate_invoice_pdf(from_name, from_email, skater, year, month, lessons, total, out_path):
    """Create an invoice PDF centered header purple; date lines and totals."""
    c = canvas.Canvas(out_path, pagesize=A4)
    width, height = A4
    margin = 20 * mm

    header_height = 80
    c.setFillColor(colors.purple)
    c.rect(0, height - header_height, width, header_height, fill=1)

    c.setFillColor(colors.white)
    c.setFont('Helvetica-Bold', 28)
    c.drawCentredString(width / 2, height - header_height + 30, "Invoice")

    # From / To placed lower so they don't touch header
    y = height - header_height - 40
    c.setFillColor(colors.black)

    c.setFont('Helvetica-Bold', 16)
    c.drawString(margin, y, f"From: {from_name}")
    y -= 18
    c.setFont('Helvetica', 12)
    c.drawString(margin, y, f"{from_email}")
    y -= 25

    c.setFont('Helvetica', 12)
    c.drawString(margin, y, f"To: {skater['name']} ({skater['email']})")
    y -= 25

    c.setFont('Helvetica-Bold', 14)
    c.drawCentredString(width / 2, y, f"Invoice for {datetime(year, month, 1).strftime('%B %Y')}")
    y -= 25

    # Column headers
    columns = ['Date', 'Lesson Type', 'Amount']
    col_positions = [margin + 40, margin + 160, width - margin - 40]
    c.setFont('Helvetica-Bold', 12)
    for col, pos in zip(columns, col_positions):
        if col != 'Amount':
            c.drawCentredString(pos, y, col)
        else:
            c.drawRightString(pos, y, col)
    y -= 12
    c.line(margin, y, width - margin, y)
    y -= 22

    c.setFont('Helvetica', 12)
    for lesson in lessons:
        if y < 60 * mm:
            c.showPage()
            y = height - margin
        dt = datetime.fromisoformat(lesson['date'])
        date_str = dt.strftime('%B %d, %Y')
        c.drawCentredString(col_positions[0], y, date_str)
        c.drawCentredString(col_positions[1], y, lesson['lesson_type'])
        c.drawRightString(col_positions[2], y, f"${lesson['amount']:.2f}")
        y -= 22

    y -= 8
    c.line(margin, y, width - margin, y)
    y -= 25
    c.setFont('Helvetica-Bold', 12)
    c.drawRightString(col_positions[2], y, f"TOTAL: ${total:.2f}")
    c.save()

# ---------- App ----------
class SkatingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Skating Invoicer")
        self.geometry("1000x640")
        init_db()
        self.load_update_settings()
        self.create_widgets()
        self.refresh_skaters()
        self.refresh_lesson_types()
        self.refresh_finance_view()

    # ---------- UI ----------
    def create_widgets(self):
        main = ttk.Frame(self)
        main.pack(fill='both', expand=True, padx=8, pady=8)

        # LEFT panel: skaters & update settings & admin
        left = ttk.Frame(main, width=280)
        left.pack(side='left', fill='y')

        ttk.Label(left, text='Skaters').pack(anchor='nw')
        self.skater_var = tk.StringVar()
        self.skater_menu = ttk.Combobox(left, textvariable=self.skater_var, state='readonly')
        self.skater_menu.pack(fill='x', padx=4, pady=2)
        self.skater_menu.bind('<<ComboboxSelected>>', lambda e: self.on_skater_selected())

        ttk.Button(left, text='Add Skater', command=self.add_skater_dialog).pack(fill='x', pady=4, padx=4)
        ttk.Button(left, text='Edit Selected Skater', command=self.edit_skater_dialog).pack(fill='x', pady=4, padx=4)
        ttk.Button(left, text='Manage Lesson Types', command=self.manage_lesson_types_popup).pack(fill='x', pady=4, padx=4)

        # Update Settings (kept)
        ttk.Label(left, text="Update Settings").pack(pady=(18,2), anchor='w', padx=6)
        self.update_url_var = tk.StringVar(value=self.update_settings.get('update_url',''))
        ttk.Entry(left, textvariable=self.update_url_var).pack(fill='x', padx=6, pady=2)
        ttk.Button(left, text="Check for Updates", command=self.check_updates).pack(fill='x', padx=6, pady=2)

        # Admin button
        ttk.Button(left, text="Admin Panel", command=self.admin_login).pack(fill='x', pady=(20,4), padx=6)

        # CENTER: tabs
        center = ttk.Frame(main)
        center.pack(side='left', fill='both', expand=True, padx=(12,0))
        self.tabs = ttk.Notebook(center)
        self.tabs.pack(fill='both', expand=True)

        # Lessons tab
        self.tab_lessons = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_lessons, text='Lessons')
        self.build_lessons_tab()

        # Invoice tab (uses selected skater on LEFT)
        self.tab_invoice = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_invoice, text='Generate Invoice')
        self.build_invoice_tab()

        # Finance Manager tab
        self.tab_finance = ttk.Frame(self.tabs)
        self.tabs.add(self.tab_finance, text='Finance Manager')
        self.build_finance_tab()

    # ---------- Lessons Tab ----------
    def build_lessons_tab(self):
        frame = self.tab_lessons
        pad = {'padx':6, 'pady':6}

        ttk.Label(frame, text='Selected Skater:').grid(row=0, column=0, sticky='w', **pad)
        self.selected_skater_label = ttk.Label(frame, text='(none)')
        self.selected_skater_label.grid(row=0, column=1, sticky='w', **pad)

        ttk.Label(frame, text='Amount:').grid(row=1, column=0, sticky='w', **pad)
        self.lesson_amount = ttk.Entry(frame)
        self.lesson_amount.insert(0, '30')
        self.lesson_amount.grid(row=1, column=1, sticky='w', **pad)

        ttk.Label(frame, text='Date (YYYY-MM-DD):').grid(row=2, column=0, sticky='w', **pad)
        self.lesson_date = ttk.Entry(frame)
        self.lesson_date.insert(0, date.today().isoformat())
        self.lesson_date.grid(row=2, column=1, sticky='w', **pad)

        ttk.Label(frame, text='Lesson Type:').grid(row=3, column=0, sticky='w', **pad)
        self.lesson_type_var = tk.StringVar()
        self.lesson_type_menu = ttk.Combobox(frame, textvariable=self.lesson_type_var, state='readonly')
        self.lesson_type_menu.grid(row=3, column=1, sticky='w', **pad)

        add_btn = tk.Button(frame, text='Add Lesson', command=self.add_lesson, bg='green', fg='white', font=('Helvetica',12,'bold'))
        add_btn.grid(row=4, column=0, columnspan=2, sticky='ew', **pad)

        self.lessons_label = ttk.Label(frame, text='Lessons for (none)')
        self.lessons_label.grid(row=5, column=0, columnspan=2, sticky='w', **pad)

        self.lessons_list = tk.Listbox(frame, height=16)
        self.lessons_list.grid(row=6, column=0, columnspan=2, sticky='nsew', **pad)
        frame.rowconfigure(6, weight=1)
        self.lessons_list.bind("<Button-3>", self.lesson_right_click)

    # ---------- Invoice Tab ----------
    def build_invoice_tab(self):
        frame = self.tab_invoice
        pad = {'padx':6, 'pady':6}

        # From name & email fields (same as before)
        ttk.Label(frame, text="From:").grid(row=0,column=0, **pad)
        self.from_name_var = tk.StringVar(value="Helene Carle")
        ttk.Entry(frame,textvariable=self.from_name_var).grid(row=0,column=1, **pad)

        ttk.Label(frame, text="From Email:").grid(row=1,column=0, **pad)
        self.from_email_var = tk.StringVar(value="skatersis2001@gmail.com")
        ttk.Entry(frame,textvariable=self.from_email_var).grid(row=1,column=1, **pad)

        # Note: no skater selector here — uses the selected skater from the left
        ttk.Label(frame, text="(Invoice will be generated for the skater selected on the left)").grid(row=2,column=0,columnspan=2, **pad)

        ttk.Label(frame, text="Month (1-12):").grid(row=3,column=0, **pad)
        self.invoice_month_var = tk.StringVar(value=str(date.today().month))
        ttk.Entry(frame,textvariable=self.invoice_month_var).grid(row=3,column=1, **pad)

        ttk.Label(frame, text="Year (YYYY):").grid(row=4,column=0, **pad)
        self.invoice_year_var = tk.StringVar(value=str(date.today().year))
        ttk.Entry(frame,textvariable=self.invoice_year_var).grid(row=4,column=1, **pad)

        ttk.Button(frame,text="Generate PDF Invoice",command=self.generate_invoice).grid(row=5,column=0,columnspan=2,pady=10)

    # ---------- Finance Manager Tab ----------
    def build_finance_tab(self):
        frame = self.tab_finance
        pad = {'padx':6, 'pady':6}

        ttk.Label(frame, text="Manage Skaters (Paid checkbox)").pack(anchor='w', **pad)

        # scrolling frame for skaters with checkboxes
        container = ttk.Frame(frame)
        container.pack(fill='both', expand=True, padx=6, pady=4)
        canvas_frame = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(container, orient='vertical', command=canvas_frame.yview)
        self.finance_inner = ttk.Frame(canvas_frame)

        self.finance_inner.bind(
            "<Configure>",
            lambda e: canvas_frame.configure(scrollregion=canvas_frame.bbox("all"))
        )
        canvas_frame.create_window((0,0), window=self.finance_inner, anchor='nw')
        canvas_frame.configure(yscrollcommand=scrollbar.set)

        canvas_frame.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # Bottom summary (expected revenue, collected revenue)
        bottom = ttk.Frame(frame)
        bottom.pack(fill='x', pady=8, padx=6)
        ttk.Label(bottom, text="Expected revenue:").grid(row=0, column=0, sticky='e')
        self.expected_var = tk.StringVar(value="$0.00")
        ttk.Label(bottom, textvariable=self.expected_var, font=('Helvetica',10,'bold')).grid(row=0, column=1, sticky='w', padx=6)

        ttk.Label(bottom, text="Collected revenue:").grid(row=1, column=0, sticky='e')
        self.collected_var = tk.StringVar(value="$0.00")
        ttk.Label(bottom, textvariable=self.collected_var, font=('Helvetica',10,'bold')).grid(row=1, column=1, sticky='w', padx=6)

        ttk.Button(frame, text="Refresh Finance View", command=self.refresh_finance_view).pack(pady=(6,0))

    # ---------- CRUD / Refresh ----------
    def refresh_skaters(self):
        rows = run_query('SELECT id,name,email,paid FROM skaters ORDER BY name', fetch=True)
        self.skaters = [{'id':r[0],'name':r[1],'email':r[2],'paid':r[3]} for r in rows]
        self.skater_menu['values'] = [s['name'] for s in self.skaters]
        # If selected skater index remains valid, keep selection
        selname = self.skater_var.get()
        if selname in [s['name'] for s in self.skaters]:
            self.skater_menu.set(selname)
        else:
            # clear selection
            if self.skaters:
                self.skater_menu.set('')
                self.selected_skater = None
                self.selected_skater_label.config(text='(none)')
        # refresh finance panel UI if visible
        self.refresh_finance_view()

    def refresh_lesson_types(self):
        rows = run_query('SELECT id,name,rate FROM lesson_types ORDER BY name', fetch=True)
        self.lesson_types = [{'id':r[0],'name':r[1],'rate':r[2]} for r in rows]
        # update combobox values
        try:
            self.lesson_type_menu['values'] = [lt['name'] for lt in self.lesson_types]
        except Exception:
            pass

    # Finance view refresh (rebuild inner widgets)
    def refresh_finance_view(self):
        # clear finance inner frame
        if hasattr(self, 'finance_inner'):
            for w in self.finance_inner.winfo_children():
                w.destroy()

        # reload skaters
        self.refresh_reduced_skaters()

        # create a row per skater with checkbox
        self.paid_vars = {}
        for i, sk in enumerate(self.skaters):
            frm = ttk.Frame(self.finance_inner)
            frm.grid(row=i, column=0, sticky='ew', pady=2, padx=4)
            lbl = ttk.Label(frm, text=sk['name'])
            lbl.pack(side='left', padx=(0,8))
            var = tk.IntVar(value=1 if sk.get('paid') else 0)
            chk = ttk.Checkbutton(frm, text='Paid', variable=var,
                                  command=lambda sid=sk['id'], v=var: self.toggle_paid(sid, v.get()))
            chk.pack(side='left')
            self.paid_vars[sk['id']] = var

        # recalc totals
        expected = self.calculate_expected_revenue()
        collected = self.calculate_collected_revenue()
        self.expected_var.set(f"${expected:.2f}")
        self.collected_var.set(f"${collected:.2f}")

    def refresh_reduced_skaters(self):
        # helper to refresh skaters list in memory (without touching UI)
        rows = run_query('SELECT id,name,email,paid FROM skaters ORDER BY name', fetch=True)
        self.skaters = [{'id':r[0],'name':r[1],'email':r[2],'paid':r[3]} for r in rows]

    def on_skater_selected(self):
        sel = self.skater_menu.current()
        if sel < 0:
            self.selected_skater = None
            self.selected_skater_label.config(text='(none)')
            self.lessons_label.config(text='Lessons for (none)')
            self.lessons_list.delete(0, tk.END)
            return
        self.selected_skater = self.skaters[sel]
        self.selected_skater_label.config(text=f"{self.selected_skater['name']} ({self.selected_skater['email']})")
        self.lessons_label.config(text=f"Lessons for {self.selected_skater['name']}")
        self.refresh_lessons_list()

    def refresh_lessons_list(self):
        if not hasattr(self,'selected_skater') or not self.selected_skater:
            self.lessons_list.delete(0,tk.END)
            return
        skater_id = self.selected_skater['id']
        rows = run_query('''SELECT l.id,l.date,l.amount,lt.name FROM lessons l
                            JOIN lesson_types lt ON l.lesson_type_id=lt.id
                            WHERE l.skater_id=? ORDER BY l.date DESC''',(skater_id,),fetch=True)
        self.lessons_list.delete(0,tk.END)
        for r in rows:
            try:
                dt = datetime.fromisoformat(r[1])
                date_str = dt.strftime('%B %d, %Y')
            except Exception:
                date_str = r[1]
            self.lessons_list.insert(tk.END,f"{r[0]} | {date_str} | {r[3]} | ${r[2]:.2f}")

    # ---------- Skater dialogs ----------
    def add_skater_dialog(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Skater")
        ttk.Label(dlg,text="Name").grid(row=0,column=0, padx=6, pady=6)
        e_name = ttk.Entry(dlg); e_name.grid(row=0,column=1, padx=6, pady=6)
        ttk.Label(dlg,text="Email").grid(row=1,column=0, padx=6, pady=6)
        e_email = ttk.Entry(dlg); e_email.grid(row=1,column=1, padx=6, pady=6)
        def save():
            name=e_name.get().strip(); email=e_email.get().strip()
            if not name or not email:
                messagebox.showerror("Missing","Provide name & email"); return
            run_query('INSERT INTO skaters(name,email,paid) VALUES(?,?,0)',(name,email))
            dlg.destroy(); self.refresh_skaters()
        ttk.Button(dlg,text="Save",command=save).grid(row=2,column=0,columnspan=2,pady=8)

    def edit_skater_dialog(self):
        if not hasattr(self,'selected_skater') or not self.selected_skater:
            messagebox.showinfo("Select Skater","Select a skater first"); return
        skater=self.selected_skater
        dlg=tk.Toplevel(self)
        dlg.title("Edit Skater")
        ttk.Label(dlg,text="Name").grid(row=0,column=0,padx=6,pady=6)
        e_name=ttk.Entry(dlg); e_name.grid(row=0,column=1,padx=6,pady=6); e_name.insert(0,skater['name'])
        ttk.Label(dlg,text="Email").grid(row=1,column=0,padx=6,pady=6)
        e_email=ttk.Entry(dlg); e_email.grid(row=1,column=1,padx=6,pady=6); e_email.insert(0,skater['email'])
        def save():
            name=e_name.get().strip(); email=e_email.get().strip()
            if not name or not email:
                messagebox.showerror("Missing","Provide name & email"); return
            run_query('UPDATE skaters SET name=?,email=? WHERE id=?',(name,email,skater['id']))
            dlg.destroy(); self.refresh_skaters()
        ttk.Button(dlg,text="Save",command=save).grid(row=2,column=0,columnspan=2,pady=8)

    # ---------- Manage Lesson Types ----------
    def manage_lesson_types_popup(self):
        dlg = tk.Toplevel(self)
        dlg.title("Lesson Types")
        lt_list = tk.Listbox(dlg)
        lt_list.pack(fill='both',expand=True,padx=6,pady=6)
        rows = run_query('SELECT id,name,rate FROM lesson_types ORDER BY name', fetch=True)
        lesson_types = [{'id':r[0],'name':r[1],'rate':r[2]} for r in rows]
        for lt in lesson_types:
            lt_list.insert(tk.END,f"{lt['name']} | ${lt['rate']:.2f}")
        def add_lt():
            name=simpledialog.askstring("Name","Lesson Name",parent=dlg)
            rate=simpledialog.askfloat("Rate","Hourly Rate",parent=dlg)
            if name and rate is not None:
                run_query('INSERT INTO lesson_types(name,rate) VALUES(?,?)',(name,rate))
                dlg.destroy(); self.manage_lesson_types_popup()
        ttk.Button(dlg,text="Add Lesson Type",command=add_lt).pack(fill='x', padx=6, pady=(0,6))

    # ---------- Lessons ----------
    def add_lesson(self):
        if not hasattr(self,'selected_skater') or not self.selected_skater:
            messagebox.showinfo("Select Skater","Select a skater first"); return
        try:
            amount=float(self.lesson_amount.get())
            dt=datetime.fromisoformat(self.lesson_date.get())
            lesson_type_name=self.lesson_type_var.get()
            lt=[lt for lt in self.lesson_types if lt['name']==lesson_type_name]
            if not lt:
                messagebox.showerror("Missing","Select a lesson type"); return
            lt = lt[0]
            run_query('INSERT INTO lessons(skater_id,date,amount,lesson_type_id) VALUES(?,?,?,?)',
                      (self.selected_skater['id'], dt.isoformat(), amount, lt['id']))
            self.refresh_lessons_list()
        except ValueError:
            messagebox.showerror("Bad input","Amount must be a number and date must be YYYY-MM-DD")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def lesson_right_click(self,event):
        try:
            index=self.lessons_list.nearest(event.y)
            self.lessons_list.selection_clear(0,tk.END)
            self.lessons_list.selection_set(index)
            menu=tk.Menu(self, tearoff=0)
            menu.add_command(label="Delete Lesson", command=lambda:self.delete_lesson(index))
            menu.add_command(label="Edit Lesson", command=lambda:self.edit_lesson(index))
            menu.tk_popup(event.x_root, event.y_root)
        except Exception as e:
            print(e)

    def delete_lesson(self,index):
        try:
            sel=self.lessons_list.get(index)
            lesson_id=int(sel.split("|")[0].strip())
            if messagebox.askyesno("Delete Lesson", f"Delete lesson {lesson_id}?"):
                run_query('DELETE FROM lessons WHERE id=?',(lesson_id,))
                self.refresh_lessons_list()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def edit_lesson(self,index):
        sel=self.lessons_list.get(index)
        lesson_id=int(sel.split("|")[0].strip())
        row=run_query('SELECT date,amount,lesson_type_id FROM lessons WHERE id=?',(lesson_id,),fetch=True)[0]
        dt_str, amount, lt_id = row
        dlg=tk.Toplevel(self)
        dlg.title("Edit Lesson")
        ttk.Label(dlg,text="Amount").grid(row=0,column=0,padx=6,pady=6)
        e_amount=ttk.Entry(dlg); e_amount.grid(row=0,column=1,padx=6,pady=6); e_amount.insert(0,str(amount))
        ttk.Label(dlg,text="Date (YYYY-MM-DD)").grid(row=1,column=0,padx=6,pady=6)
        e_date=ttk.Entry(dlg); e_date.grid(row=1,column=1,padx=6,pady=6); e_date.insert(0,dt_str[:10])
        ttk.Label(dlg,text="Lesson Type").grid(row=2,column=0,padx=6,pady=6)
        lt_names=[lt['name'] for lt in self.lesson_types]
        lt_var=tk.StringVar(value=[lt['name'] for lt in self.lesson_types if lt['id']==lt_id][0])
        lt_menu=ttk.Combobox(dlg,textvariable=lt_var,values=lt_names,state='readonly'); lt_menu.grid(row=2,column=1,padx=6,pady=6)
        def save():
            try:
                run_query('UPDATE lessons SET date=?,amount=?,lesson_type_id=? WHERE id=?',
                          (e_date.get(),float(e_amount.get()),[lt['id'] for lt in self.lesson_types if lt['name']==lt_var.get()][0],lesson_id))
                dlg.destroy(); self.refresh_lessons_list()
            except ValueError:
                messagebox.showerror("Bad input","Amount must be a number")
        ttk.Button(dlg,text="Save",command=save).grid(row=3,column=0,columnspan=2,pady=8)

    # ---------- Invoice ----------
    def generate_invoice(self):
        if not hasattr(self,'selected_skater') or not self.selected_skater:
            messagebox.showinfo("Select Skater","Select a skater on the left first"); return
        skater = self.selected_skater
        try:
            month = int(self.invoice_month_var.get())
            year = int(self.invoice_year_var.get())
        except Exception:
            messagebox.showerror("Bad input","Month and Year must be integers"); return
        from_name = self.from_name_var.get()
        from_email = self.from_email_var.get()
        rows = run_query('''
            SELECT l.date,l.amount,lt.name
            FROM lessons l
            JOIN lesson_types lt ON l.lesson_type_id=lt.id
            WHERE l.skater_id=? AND strftime('%Y',l.date)=? AND strftime('%m',l.date)=?
            ORDER BY l.date
        ''',(skater['id'],str(year),f"{month:02d}"),fetch=True)
        lessons=[{'date':r[0],'amount':r[1],'lesson_type':r[2]} for r in rows]
        total = sum(r['amount'] for r in lessons)
        out_path = os.path.join(INVOICE_DIR, f"{skater['name']}_{year}_{month}.pdf")
        generate_invoice_pdf(from_name, from_email, skater, year, month, lessons, total, out_path)
        messagebox.showinfo("Invoice Generated", f"Invoice saved to {out_path}")

    # ---------- Finance calculations ----------
    def calculate_expected_revenue(self):
        rows = run_query('SELECT SUM(amount) FROM lessons', fetch=True)
        total = rows[0][0] if rows and rows[0][0] is not None else 0.0
        return total

    def calculate_collected_revenue(self):
        # Sum amounts for lessons where skater.paid=1
        rows = run_query('''
            SELECT SUM(l.amount) FROM lessons l
            JOIN skaters s ON l.skater_id = s.id
            WHERE s.paid = 1
        ''', fetch=True)
        total = rows[0][0] if rows and rows[0][0] is not None else 0.0
        return total

    def toggle_paid(self, skater_id, paid_value):
        try:
            run_query('UPDATE skaters SET paid=? WHERE id=?', (1 if paid_value else 0, skater_id))
            # refresh finance totals and skater list
            self.refresh_reduced_skaters()
            self.expected_var.set(f"${self.calculate_expected_revenue():.2f}")
            self.collected_var.set(f"${self.calculate_collected_revenue():.2f}")
            # also refresh left skater listing
            self.refresh_skaters()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---------- Update settings ----------
    def load_update_settings(self):
        if os.path.exists(UPDATE_SETTINGS_FILE):
            with open(UPDATE_SETTINGS_FILE,'r') as f:
                try:
                    self.update_settings = json.load(f)
                except Exception:
                    self.update_settings = {'update_url':''}
        else:
            self.update_settings = {'update_url':''}

    def save_update_settings(self):
        self.update_settings['update_url'] = self.update_url_var.get()
        with open(UPDATE_SETTINGS_FILE,'w') as f:
            json.dump(self.update_settings,f)

    def check_updates(self):
        self.save_update_settings()
        url = self.update_settings.get('update_url')
        if not url:
            messagebox.showinfo("No URL","Please provide a URL for updates.")
            return
        try:
            resp = urllib.request.urlopen(url, timeout=10)
            data = json.loads(resp.read())
            new_version = data.get('version')
            download_url = data.get('download_url')
            if new_version:
                messagebox.showinfo("Update Available", f"Version {new_version} available!\nDownload: {download_url}\nWiFi required.")
            else:
                messagebox.showinfo("No Update","No update information found in the provided URL.")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Update Error", f"Error fetching update: {e}")

    # ---------- Admin ----------
    def admin_login(self):
        username = simpledialog.askstring("Admin Login", "Administrator username:", parent=self)
        if username is None:
            return
        password = simpledialog.askstring("Admin Login", "Administrator password:", parent=self, show='*')
        if password is None:
            return
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            self.open_admin_panel()
        else:
            messagebox.showerror("Admin", "Incorrect username or password.")

    def open_admin_panel(self):
        dlg = tk.Toplevel(self)
        dlg.title("Admin Panel")
        dlg.geometry("420x220")
        ttk.Label(dlg, text="Admin Panel", font=('Helvetica',14,'bold')).pack(pady=(8,6))
        # placeholder for future admin functions
        ttk.Label(dlg, text="(No email features — removed)").pack(pady=(4,6))
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=(8,12))

if __name__ == "__main__":
    app = SkatingApp()
    app.mainloop()

import os
import sqlite3
from datetime import datetime
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, redirect

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / 'gurukrupa-website'
DB_PATH = BASE_DIR / 'orders.db'

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path='')

CREATE_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    product TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    mode TEXT NOT NULL,
    notes TEXT,
    status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL
);
'''

CREATE_CONTACT_SQL = '''
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);
'''


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_db_connection() as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.execute(CREATE_CONTACT_SQL)
        conn.commit()


@app.route('/')
def index():
    return redirect('/index.html')


@app.route('/orders', methods=['POST'])
def create_order():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400

    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    product = data.get('product', '').strip()
    quantity = int(data.get('quantity') or 1)
    mode = data.get('mode', 'online').strip()
    notes = data.get('notes', '').strip()

    if not name or not phone or not product:
        return jsonify({'success': False, 'error': 'Name, phone, and product are required.'}), 400

    created_at = datetime.utcnow().isoformat()
    with get_db_connection() as conn:
        cursor = conn.execute(
            'INSERT INTO orders (name, phone, product, quantity, mode, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, phone, product, quantity, mode, notes, created_at),
        )
        conn.commit()
        order_id = cursor.lastrowid

    return jsonify({'success': True, 'order_id': order_id})


@app.route('/admin/orders/update/<int:order_id>', methods=['POST'])
def update_order_status(order_id):
    data = request.get_json(force=True, silent=True) or {}
    status = data.get('status', 'pending').strip()
    if status not in ['pending', 'confirmed', 'completed', 'cancelled']:
        status = 'pending'
    with get_db_connection() as conn:
        conn.execute('UPDATE orders SET status = ? WHERE id = ?', (status, order_id))
        conn.commit()
    return jsonify({'success': True, 'order_id': order_id, 'status': status})


@app.route('/contact', methods=['POST'])
def create_contact():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'success': False, 'error': 'Invalid JSON data'}), 400

    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    message = data.get('message', '').strip()

    if not name or not message:
        return jsonify({'success': False, 'error': 'Name and message are required.'}), 400

    created_at = datetime.utcnow().isoformat()
    with get_db_connection() as conn:
        cursor = conn.execute(
            'INSERT INTO contacts (name, email, phone, message, created_at) VALUES (?, ?, ?, ?, ?)',
            (name, email, phone, message, created_at),
        )
        conn.commit()
        contact_id = cursor.lastrowid

    return jsonify({'success': True, 'contact_id': contact_id})


@app.route('/admin/orders', methods=['GET'])
def list_orders():
    with get_db_connection() as conn:
        rows = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    orders = [dict(row) for row in rows]
    return jsonify({'orders': orders})


@app.route('/admin/contacts', methods=['GET'])
def list_contacts():
    with get_db_connection() as conn:
        rows = conn.execute('SELECT * FROM contacts ORDER BY created_at DESC').fetchall()
    contacts = [dict(row) for row in rows]
    return jsonify({'contacts': contacts})


@app.route('/admin')
def admin_dashboard():
    return '''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>GURUKRUPA Admin Dashboard</title>
  <style>
    body{font-family:Arial,sans-serif;background:#f5f5f5;color:#222;margin:0;padding:24px}
    h1{margin-top:0;color:#1a1610}
    .section{background:#fff;padding:20px;border-radius:14px;box-shadow:0 15px 40px rgba(0,0,0,0.08);margin-bottom:24px}
    table{width:100%;border-collapse:collapse;margin-top:12px}
    th,td{padding:12px 10px;border:1px solid #e3e3e3;text-align:left;font-size:0.95rem}
    th{background:#f8f8f8}
    .badge{display:inline-block;padding:6px 10px;border-radius:999px;font-size:0.8rem;color:#fff}
    .badge-order{background:#c8922a}
    .badge-contact{background:#27ae60}
    .badge-pending{background:#ff9800;color:#fff}
    .badge-confirmed{background:#2196f3;color:#fff}
    .badge-completed{background:#4caf50;color:#fff}
    .badge-cancelled{background:#f44336;color:#fff}
    .empty{color:#666;font-size:0.95rem}
    select{padding:6px;border:1px solid #ccc;border-radius:4px;font-size:0.9rem;cursor:pointer}
    button{padding:6px 12px;background:#c8922a;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:0.9rem}
    button:hover{background:#b8825a}
    .order-row.pending{background:#fff9f5}
    .order-row.completed{background:#f0fff0}
  </style>
</head>
<body>
  <h1>GURUKRUPA Admin Dashboard</h1>
  <div class="section">
    <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">
      <div><strong>Orders</strong></div>
      <span class="badge badge-order">Auto-updating every 10s</span>
    </div>
    <div id="ordersContainer">Loading orders…</div>
  </div>
  <div class="section">
    <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">
      <div><strong>Contact Messages</strong></div>
      <span class="badge badge-contact">Auto-updating every 10s</span>
    </div>
    <div id="contactsContainer">Loading contacts…</div>
  </div>
  <script>
    function renderOrders(rows) {
      const container = document.getElementById('ordersContainer');
      if (!rows.length) {
        container.innerHTML = '<p class="empty">No orders yet.</p>';
        return;
      }
      const header = '<tr><th>ID</th><th>Name</th><th>Phone</th><th>Product</th><th>Qty</th><th>Mode</th><th>Status</th><th>Action</th><th>Created</th></tr>';
      const body = rows.map(row => {
        const createdDate = new Date(row.created_at).toLocaleString();
        return '<tr class="order-row ' + row.status + '"><td>' + row.id + '</td><td>' + row.name + '</td><td>' + row.phone + '</td><td>' + row.product + '</td><td>' + row.quantity + '</td><td>' + row.mode + '</td><td><span class="badge badge-' + row.status + '">' + row.status.toUpperCase() + '</span></td><td><select onchange="updateStatus(' + row.id + ', this.value)"><option value="pending" ' + (row.status === 'pending' ? 'selected' : '') + '>Pending</option><option value="confirmed" ' + (row.status === 'confirmed' ? 'selected' : '') + '>Confirmed</option><option value="completed" ' + (row.status === 'completed' ? 'selected' : '') + '>Completed</option><option value="cancelled" ' + (row.status === 'cancelled' ? 'selected' : '') + '>Cancelled</option></select></td><td>' + createdDate + '</td></tr>';
      }).join('');
      container.innerHTML = '<table>' + header + body + '</table>';
    }
    function renderContacts(rows) {
      const container = document.getElementById('contactsContainer');
      if (!rows.length) {
        container.innerHTML = '<p class="empty">No contact messages yet.</p>';
        return;
      }
      const header = '<tr><th>ID</th><th>Name</th><th>Email</th><th>Phone</th><th>Message</th><th>Received</th></tr>';
      const body = rows.map(row => {
        const createdDate = new Date(row.created_at).toLocaleString();
        return '<tr><td>' + row.id + '</td><td>' + row.name + '</td><td>' + (row.email || '-') + '</td><td>' + (row.phone || '-') + '</td><td>' + row.message + '</td><td>' + createdDate + '</td></tr>';
      }).join('');
      container.innerHTML = '<table>' + header + body + '</table>';
    }
    function updateStatus(orderId, status) {
      fetch('/admin/orders/update/' + orderId, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({status: status})
      }).then(() => refresh());
    }
    function refresh() {
      fetch('/admin/orders').then(r=>r.json()).then(data => {
        renderOrders(data.orders || []);
      });
      fetch('/admin/contacts').then(r=>r.json()).then(data => {
        renderContacts(data.contacts || []);
      });
    }
    refresh();
    setInterval(refresh, 10000);
  </script>
</body>
</html>'''


if __name__ == '__main__':
    init_db()
import os            
app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 8000)))


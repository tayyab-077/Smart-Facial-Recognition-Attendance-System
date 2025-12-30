// admin.js — shared admin actions for users, attendance, pending approvals
// Works with admin_dashboard.html, admin_attendance.html

// ----------------------
// Helper functions
// ----------------------

// GET JSON helper
async function getJson(url) {
    const res = await fetch(url, { credentials: 'same-origin' });
    if (!res.ok) throw new Error('Request failed: ' + res.status);
    return res.json();
}

// POST JSON helper
async function postJson(url, data) {
    const res = await fetch(url, {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    return res.json();
}

// Escape HTML for safe rendering
function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    }[c]));
}

// Format date for display
function formatDate(dt) {
    if (!dt) return "—";
    const d = new Date(dt.replace(" ", "T"));
    return isNaN(d) ? dt : d.toLocaleString();
}

// ----------------------
// Pending enrollments
// ----------------------
async function loadPendingTo(containerId = 'pendingList') {
    try {
        const arr = await getJson('/api/admin/pending');
        const ul = document.getElementById(containerId);
        if (!ul) return;
        ul.innerHTML = '';

        if (!arr.length) {
            const li = document.createElement('li');
            li.innerText = 'No pending enrollments';
            li.style.fontStyle = 'italic';
            ul.appendChild(li);
            return;
        }

        arr.forEach(p => {
            const li = document.createElement('li');
            li.innerHTML = `
                ${escapeHtml(p.name)} —
                <button onclick="adminApprove('${p.id}')">Approve</button>
                <button onclick="adminReject('${p.id}')">Reject</button>
            `;
            ul.appendChild(li);
        });
    } catch (e) {
        console.error(e);
        alert('Failed to load pending enrollments');
    }
}

async function adminApprove(id) {
    try {
        const res = await postJson('/api/admin/approve', { pending_id: id });
        if (res.status === 'approved') {
            alert(`Approved: User ID ${res.user_id}`);
        } else if (res.error) {
            alert(`Error: ${res.error}`);
        } else {
            alert('Approval failed');
        }
    } catch (e) {
        console.error(e);
        alert('Approval request failed');
    } finally {
        if (typeof loadPendingTo === 'function') loadPendingTo();
        if (typeof loadUsers === 'function') loadUsers();
    }
}

async function adminReject(id) {
    try {
        await postJson('/api/admin/reject', { pending_id: id });
        alert(`Rejected pending enrollment ID ${id}`);
    } catch (e) {
        console.error(e);
        alert('Rejection failed');
    } finally {
        if (typeof loadPendingTo === 'function') loadPendingTo();
    }
}

// ----------------------
// Users management
// ----------------------
async function loadUsers() {
    try {
        const users = await getJson('/api/admin/users');
        const tbody = document.querySelector('#usersTable tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        users.forEach(u => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${u.id}</td>
                <td><input id="name_${u.id}" value="${escapeHtml(u.name)}" /></td>
                <td>${u.attendance_count ?? 0}</td>
                <td>${u.created_at ? formatDate(u.created_at) : 'N/A'}</td>
                <td>
                    <button onclick="updateUser(${u.id})">Save</button>
                    <button onclick="viewUserAttendance(${u.id})">View</button>
                    <button onclick="deleteUser(${u.id})" style="background:#c62828;color:#fff">Delete</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error(e);
        alert('Failed to load users');
    }
}

async function updateUser(id) {
    const input = document.getElementById(`name_${id}`);
    if (!input) return;
    const name = input.value.trim();
    if (!name) return alert('Name required');
    await postJson('/api/admin/update_user', { id, name });
    loadUsers();
}

async function deleteUser(id) {
    if (!confirm('Delete user and all attendance & images?')) return;
    await postJson('/api/admin/delete_user', { id });
    loadUsers();
}

async function viewUserAttendance(id) {
    const res = await postJson('/api/user/attendance', { user_id: id });
    showAttendanceModal(id, res);
}

// ----------------------
// Admin attendance filter
// ----------------------
async function loadAttendance() {
    const date = (document.getElementById('filterDate') || {}).value || '';
    const user = (document.getElementById('filterUser') || {}).value || '';
    const device = (document.getElementById('filterDevice') || {}).value || '';
    const payload = {};
    if (date) payload.date = date;
    if (user) payload.user_id = user;
    if (device) payload.device = device;

    try {
        const rows = await postJson('/api/admin/attendance', payload);
        const tbody = document.querySelector('#attTable tbody');
        if (!tbody) return;
        tbody.innerHTML = '';
        rows.forEach(r => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${r.user_id}</td><td>${escapeHtml(r.name)}</td><td>${r.timestamp}</td><td>${r.device}</td>`;
            tbody.appendChild(tr);
        });
    } catch (e) {
        console.error(e);
        alert('Failed to load attendance');
    }
}

function exportCSV() {
    const rows = Array.from(document.querySelectorAll('#attTable tr')).map(tr =>
        Array.from(tr.querySelectorAll('th,td')).map(td =>
            `"${(td.innerText || '').replace(/"/g, '""')}"`
        ).join(',')
    );
    const csv = rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `attendance_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
}

// ----------------------
// Modal for viewing attendance
// ----------------------
function showAttendanceModal(id, items) {
    const modal = document.getElementById('attendanceModal');
    if (!modal) return;
    modal.style.display = 'block';
    document.getElementById('modalTitle').innerText = `Attendance for user ${id}`;
    const ul = document.getElementById('modalList'); 
    ul.innerHTML = '';
    (items || []).forEach(it => {
        const li = document.createElement('li');
        li.innerText = `${it.timestamp} (${it.device||''})`;
        ul.appendChild(li);
    });
}

function hideModal() {
    const modal = document.getElementById('attendanceModal');
    if (!modal) return;
    modal.style.display = 'none';
}

// ----------------------
// Auto-run loaders if page has elements
// ----------------------
if (document.getElementById('pendingList')) loadPendingTo('pendingList');
if (document.querySelector('#usersTable')) loadUsers();
if (document.getElementById('attTable')) loadAttendance();

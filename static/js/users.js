// ----------------------
// Users page JS
// ----------------------

const usersTable = document.getElementById("usersTableList");

// ----------------------
// Save admin note
// ----------------------
async function saveAdminNote(textarea) {
    const userId = textarea.dataset.user;
    const note = textarea.value.trim();

    try {
        const res = await fetch("/api/user/save_note", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: userId, note })
        });
        const data = await res.json();
        if (!data || !data.status) console.error("Note save failed");
    } catch (e) {
        console.error(e);
    }
}

// ----------------------
// Filter users
// ----------------------
function filterUsers() {
    const input = document.getElementById("searchInput").value.toLowerCase();
    const rows = usersTable.querySelectorAll("tbody tr");

    rows.forEach(r => {
        const name = r.cells[1].innerText.toLowerCase();
        const id = r.cells[0].innerText.toLowerCase();
        r.style.display = (name.includes(input) || id.includes(input)) ? "" : "none";
    });
}

// ----------------------
// Export users to Excel/CSV
// ----------------------
function exportUsersToExcel() {
    const rows = Array.from(usersTable.querySelectorAll("tr"));
    const csv = rows.map(r => {
        return Array.from(r.querySelectorAll("th,td"))
            .map(c => `"${c.innerText.replace(/"/g, '""')}"`)
            .join(",");
    }).join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = "users.csv";
    a.click();
    URL.revokeObjectURL(url);
}

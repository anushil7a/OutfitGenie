// My Outfits page JS

document.addEventListener('DOMContentLoaded', () => {
    // Toolbar buttons
    const selAll = document.getElementById('select-all');
    const desAll = document.getElementById('deselect-all');
    const favSel = document.getElementById('favorite-selected');
    const delSel = document.getElementById('delete-selected');
    const boxes = () => Array.from(document.querySelectorAll('input.outfit-checkbox'));

    // Select all
    selAll?.addEventListener('click', () => boxes().forEach(cb => cb.checked = true));
    // Deselect all
    desAll?.addEventListener('click', () => boxes().forEach(cb => cb.checked = false));

    // Favorite selected
    favSel?.addEventListener('click', async () => {
        const ids = boxes().filter(cb => cb.checked).map(cb => cb.dataset.outfitId);
        if (!ids.length) return alert('Select at least one outfit first');
        for (const id of ids) await window.toggleFavorite(id);
        boxes().forEach(cb => cb.checked = false);
    });

    // Delete selected
    delSel?.addEventListener('click', async () => {
        const ids = boxes().filter(cb => cb.checked).map(cb => cb.dataset.outfitId);
        if (!ids.length) return alert('Select at least one outfit first');
        if (!confirm(`Delete ${ids.length} outfit(s)? This can't be undone.`)) return;
        for (const id of ids) await window.deleteOutfit(id, false);
    });

    // Modal logic for full-size image
    const imageLinks = document.querySelectorAll('.outfit-image-link');
    const modal = document.getElementById('image-modal');
    const modalImg = document.getElementById('modal-image');
    const closeModalBtn = document.getElementById('close-modal');

    imageLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const url = link.getAttribute('data-image-url');
            modalImg.src = url;
            modal.classList.remove('hidden');
        });
    });

    function closeModal() {
        modal.classList.add('hidden');
        modalImg.src = '';
    }
    closeModalBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal();
    });
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeModal();
    });
});

// Single-card actions
window.toggleFavorite = async (id) => {
    const res = await fetch('/feedback', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content },
        body: JSON.stringify({ outfit_id: id, rating: 1 })
    });
    if (!res.ok) return alert('Failed to update favorite');
    const btn = document.querySelector(`[data-outfit-id="${id}"] .favorite-btn`);
    btn?.classList.toggle('bg-yellow-400');
    btn?.classList.toggle('text-yellow-600');
    btn?.classList.toggle('bg-white');
    btn?.classList.toggle('text-gray-600');
};

window.deleteOutfit = async (id, confirmDialog = true) => {
    if (confirmDialog && !confirm('Delete this outfit forever?')) return;
    const res = await fetch(`/delete-outfit/${id}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content }
    });
    if (!res.ok) return alert('Failed to delete outfit');
    document.querySelector(`[data-outfit-id="${id}"]`)?.remove();
    if (Array.from(document.querySelectorAll('[data-outfit-id]')).length === 0) location.reload();
}; 
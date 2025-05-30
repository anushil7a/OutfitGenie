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

    // Modal logic for full-size image (using .modal-trigger class)
    const modalTriggers = document.querySelectorAll('.modal-trigger');
    let modalContainer = document.getElementById('my-image-modal');

    if (!modalContainer) {
        modalContainer = document.createElement('div');
        modalContainer.id = 'my-image-modal';
        modalContainer.style.position = 'fixed';
        modalContainer.style.top = '0';
        modalContainer.style.left = '0';
        modalContainer.style.width = '100%';
        modalContainer.style.height = '100%';
        modalContainer.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
        modalContainer.style.display = 'none';
        modalContainer.style.justifyContent = 'center';
        modalContainer.style.alignItems = 'center';
        modalContainer.style.zIndex = '9999';
        modalContainer.style.cursor = 'pointer';
        modalContainer.style.transition = 'opacity 0.3s ease-in-out';
        modalContainer.style.opacity = '0';

        const modalImage = document.createElement('img');
        modalImage.id = 'my-modal-image';
        modalImage.style.maxWidth = '90%';
        modalImage.style.maxHeight = '90%';
        modalImage.style.objectFit = 'contain';
        modalImage.style.cursor = 'default';

        modalContainer.appendChild(modalImage);
        document.body.appendChild(modalContainer);

        modalContainer.addEventListener('click', function(event) {
            if (event.target === modalContainer) {
                modalContainer.style.opacity = '0';
                setTimeout(function() {
                    modalContainer.style.display = 'none';
                }, 300);
            }
        });
    }

    modalTriggers.forEach(function(triggerElement) {
        const imageLinkElement = triggerElement.previousElementSibling;
        let imageUrl = null;
        if (imageLinkElement && imageLinkElement.tagName === 'A') {
            const imgElement = imageLinkElement.querySelector('img');
            if (imgElement) {
                imageUrl = imgElement.src;
            }
        }
        if (imageUrl) {
            triggerElement.addEventListener('click', function() {
                const modalContainer = document.getElementById('my-image-modal');
                const modalImage = document.getElementById('my-modal-image');
                if (modalContainer && modalImage) {
                    modalImage.src = imageUrl;
                    modalContainer.style.display = 'flex';
                    setTimeout(function() {
                        modalContainer.style.opacity = '1';
                    }, 10);
                }
            });
        }
    });

    // Toggle Detected Items visibility (button switch)
    const toggleDetectedItemsBtn = document.getElementById('toggle-detected-items');
    if (toggleDetectedItemsBtn) {
        function setSwitchState(isOn) {
            toggleDetectedItemsBtn.setAttribute('aria-checked', isOn ? 'true' : 'false');
            toggleDetectedItemsBtn.classList.toggle('bg-indigo-600', isOn);
            toggleDetectedItemsBtn.classList.toggle('bg-gray-300', !isOn);
            const thumb = toggleDetectedItemsBtn.querySelector('span:not(.sr-only)');
            if (thumb) {
                thumb.classList.toggle('translate-x-5', isOn);
                thumb.classList.toggle('translate-x-0', !isOn);
            }
            // Show/hide detected items
            const detectedSections = document.querySelectorAll('.detected-items-section');
            detectedSections.forEach(section => {
                section.style.display = isOn ? '' : 'none';
            });
        }
        // Initial state: ON
        setSwitchState(true);
        toggleDetectedItemsBtn.addEventListener('click', function() {
            const isOn = toggleDetectedItemsBtn.getAttribute('aria-checked') === 'true';
            setSwitchState(!isOn);
        });
        // Keyboard accessibility
        toggleDetectedItemsBtn.addEventListener('keydown', function(e) {
            if (e.key === ' ' || e.key === 'Enter') {
                e.preventDefault();
                toggleDetectedItemsBtn.click();
            }
        });
    }
});

// Single-card actions
window.toggleFavorite = async (id) => {
    const btn = document.querySelector(`[data-outfit-id="${id}"] .favorite-btn`);
    const isFavorited = btn?.classList.contains('bg-yellow-400');
    const res = await fetch('/feedback', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content },
        body: JSON.stringify({ outfit_id: id, rating: isFavorited ? 0 : 1 })
    });
    if (!res.ok) return alert('Failed to update favorite');
    if (btn) {
        btn.classList.toggle('bg-yellow-400', !isFavorited);
        btn.classList.toggle('text-yellow-600', !isFavorited);
        btn.classList.toggle('bg-white', isFavorited);
        btn.classList.toggle('text-gray-600', isFavorited);
    }
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
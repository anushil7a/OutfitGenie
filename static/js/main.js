// Delete outfit function - defined globally
window.deleteOutfit = async (outfitId) => {
    if (!confirm('Are you sure you want to delete this outfit? This action cannot be undone.')) {
        return;
    }

    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        if (!csrfToken) {
            throw new Error('CSRF token not found');
        }

        const response = await fetch(`/delete-outfit/${outfitId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        });

        if (response.ok) {
            const outfitCard = document.querySelector(`[data-outfit-id="${outfitId}"]`);
            if (outfitCard) {
                outfitCard.remove();
                // If no outfits left, reload the page
                const remainingOutfits = document.querySelectorAll('[data-outfit-id]');
                if (remainingOutfits.length === 0) {
                    window.location.reload();
                }
            }
        } else {
            throw new Error('Failed to delete outfit');
        }
    } catch (error) {
        console.error('Error deleting outfit:', error);
        alert('Error deleting outfit. Please try again.');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const clothingUpload = document.getElementById('clothing-upload');
    const preferencesForm = document.getElementById('preferences-form');
    const recommendationsContainer = document.getElementById('recommendations');
    const uploadPreview = document.getElementById('upload-preview');
    const previewContainer = document.getElementById('preview-container');
    const confirmUpload = document.getElementById('confirm-upload');
    const selectAllBtn = document.getElementById('select-all');
    const deselectAllBtn = document.getElementById('deselect-all');
    const favoriteSelectedBtn = document.getElementById('favorite-selected');
    const deleteSelectedBtn = document.getElementById('delete-selected');
    const outfitCheckboxes = document.querySelectorAll('.outfit-checkbox');
    const selectedCount = document.getElementById('selected-count');

    let selectedFiles = [];
    let favoriteFiles = new Set();

    // Update selected count
    function updateSelectedCount() {
        const count = selectedFiles.filter(file => !file.removed).length;
        selectedCount.textContent = count;
        confirmUpload.disabled = count === 0;
    }

    // Handle clothing image selection
    clothingUpload.addEventListener('change', (e) => {
        const newFiles = Array.from(e.target.files);
        selectedFiles = [...selectedFiles, ...newFiles.map(file => ({ file, removed: false }))];
        
        if (selectedFiles.length > 0) {
            uploadPreview.classList.remove('hidden');
            
            // Only add previews for new files
            newFiles.forEach(file => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const preview = document.createElement('div');
                    preview.className = 'relative group';
                    preview.dataset.filename = file.name;
                    preview.innerHTML = `
                        <div class="relative">
                            <img src="${e.target.result}" alt="Preview" class="w-full h-48 object-cover rounded-lg">
                            <div class="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-30 transition-all duration-200 rounded-lg">
                                <div class="absolute top-2 right-2 flex space-x-2">
                                    <button class="favorite-btn bg-white text-gray-600 rounded-full p-1 hover:bg-yellow-400 hover:text-yellow-600 transition-colors duration-200" onclick="toggleFavorite('${file.name}')">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
                                        </svg>
                                    </button>
                                    <button class="delete-btn bg-white text-gray-600 rounded-full p-1 hover:bg-red-500 hover:text-white transition-colors duration-200" onclick="removeSelectedFile('${file.name}')">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                    previewContainer.appendChild(preview);
                };
                reader.readAsDataURL(file);
            });
            updateSelectedCount();
        }
    });

    // Toggle favorite status for a single outfit
    window.toggleFavorite = async (outfitId) => {
        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
            if (!csrfToken) {
                throw new Error('CSRF token not found');
            }

            const response = await fetch('/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    outfit_id: outfitId,
                    rating: 1
                })
            });

            if (response.ok) {
                const favoriteBtn = document.querySelector(`[data-outfit-id="${outfitId}"] .favorite-btn`);
                if (favoriteBtn) {
                    favoriteBtn.classList.toggle('bg-yellow-400');
                    favoriteBtn.classList.toggle('text-yellow-600');
                    favoriteBtn.classList.toggle('bg-white');
                    favoriteBtn.classList.toggle('text-gray-600');
                }
            } else {
                throw new Error('Failed to update favorite status');
            }
        } catch (error) {
            console.error('Error toggling favorite:', error);
            alert('Error updating favorite status. Please try again.');
        }
    };

    // Remove selected file
    window.removeSelectedFile = (fileName) => {
        // Mark file as removed
        const fileIndex = selectedFiles.findIndex(f => f.file.name === fileName);
        if (fileIndex !== -1) {
            selectedFiles[fileIndex].removed = true;
        }
        
        // Remove the preview element
        const preview = previewContainer.querySelector(`[data-filename="${fileName}"]`);
        if (preview) {
            preview.remove();
        }
        
        // Hide preview container if no files left
        if (selectedFiles.every(f => f.removed)) {
            uploadPreview.classList.add('hidden');
        }
        
        updateSelectedCount();
    };

    // Select all files
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', () => {
            outfitCheckboxes.forEach(checkbox => {
                checkbox.checked = true;
            });
        });
    }

    // Deselect all files
    if (deselectAllBtn) {
        deselectAllBtn.addEventListener('click', () => {
            outfitCheckboxes.forEach(checkbox => {
                checkbox.checked = false;
            });
        });
    }

    // Handle confirm upload
    if (confirmUpload) {
        confirmUpload.addEventListener('click', async () => {
            const filesToUpload = selectedFiles.filter(f => !f.removed).map(f => f.file);
            
            if (filesToUpload.length === 0) {
                alert('Please select at least one image to upload');
                return;
            }

            const formData = new FormData();
            for (let file of filesToUpload) {
                formData.append('image', file);
            }

            try {
                confirmUpload.disabled = true;
                confirmUpload.textContent = 'Uploading...';

                const response = await fetch('/upload', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content
                    },
                    body: formData
                });

                const data = await response.json();
                
                if (response.ok) {
                    alert(data.message);
                    // Reset the form
                    clothingUpload.value = '';
                    selectedFiles = [];
                    favoriteFiles.clear();
                    uploadPreview.classList.add('hidden');
                    previewContainer.innerHTML = '';
                    // Reload the page to show new uploads
                    window.location.reload();
                } else {
                    throw new Error(data.error || 'Upload failed');
                }
            } catch (error) {
                console.error('Error uploading images:', error);
                alert(error.message || 'Error uploading images. Please try again.');
            } finally {
                confirmUpload.disabled = false;
                confirmUpload.textContent = 'Upload Selected Images';
            }
        });
    }

    // Handle preferences form submission
    if (preferencesForm) {
        preferencesForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(preferencesForm);
            const preferences = {
                height: formData.get('height'),
                weight: formData.get('weight'),
                styles: Array.from(formData.getAll('styles'))
            };

            try {
                const response = await fetch('/preferences', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content
                    },
                    body: JSON.stringify(preferences)
                });

                if (response.ok) {
                    const data = await response.json();
                    alert('Preferences saved successfully!');
                } else {
                    const error = await response.json();
                    alert(error.error || 'Failed to save preferences');
                }
            } catch (error) {
                console.error('Error saving preferences:', error);
                alert('Error saving preferences. Please try again.');
            }
        });
    }

    // Get outfit recommendations
    async function getRecommendations() {
        try {
            const response = await fetch('/recommend', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content
                },
                body: JSON.stringify({
                    occasion: 'casual', // This should be dynamic based on user selection
                    weather: null // This will be fetched from the backend
                })
            });

            if (response.ok) {
                const data = await response.json();
                displayRecommendations(data.outfits);
            }
        } catch (error) {
            console.error('Error getting recommendations:', error);
        }
    }

    // Display outfit recommendations
    function displayRecommendations(outfits) {
        if (!recommendationsContainer) return;
        
        recommendationsContainer.innerHTML = '';

        outfits.forEach(outfit => {
            const outfitCard = document.createElement('div');
            outfitCard.className = 'bg-white rounded-lg shadow-md overflow-hidden';
            outfitCard.innerHTML = `
                <div class="p-4">
                    <h3 class="text-lg font-semibold mb-2">${outfit.occasion}</h3>
                    <ul class="space-y-2">
                        ${outfit.items.map(item => `<li class="text-gray-600">${item}</li>`).join('')}
                    </ul>
                    <div class="mt-4 flex justify-between">
                        <button class="text-green-600 hover:text-green-800" onclick="rateOutfit(${outfit.id}, 'like')">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5"></path>
                            </svg>
                        </button>
                        <button class="text-red-600 hover:text-red-800" onclick="rateOutfit(${outfit.id}, 'dislike')">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.736 3h4.018c.163 0 .326.02.485.06L17 4m-7 10v2a2 2 0 002 2h.095c.5 0 .905-.405.905-.905 0-.714.211-1.412.608-2.006L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5"></path>
                            </svg>
                        </button>
                        <button class="text-blue-600 hover:text-blue-800" onclick="saveOutfit(${outfit.id})">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"></path>
                            </svg>
                        </button>
                    </div>
                </div>
            `;
            recommendationsContainer.appendChild(outfitCard);
        });
    }

    // Rate an outfit
    window.rateOutfit = async (outfitId, rating) => {
        try {
            const response = await fetch('/feedback', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content
                },
                body: JSON.stringify({
                    outfit_id: outfitId,
                    rating: rating === 'like' ? 1 : -1
                })
            });

            if (response.ok) {
                console.log('Rating saved');
                // Optionally refresh recommendations
                getRecommendations();
            }
        } catch (error) {
            console.error('Error rating outfit:', error);
        }
    };

    // Save an outfit
    window.saveOutfit = async (outfitId) => {
        try {
            const response = await fetch('/save-outfit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content
                },
                body: JSON.stringify({
                    outfit_id: outfitId
                })
            });

            if (response.ok) {
                console.log('Outfit saved');
            }
        } catch (error) {
            console.error('Error saving outfit:', error);
        }
    };

    // Bulk selection functions for My Outfits page
    if (favoriteSelectedBtn) {
        favoriteSelectedBtn.addEventListener('click', async () => {
            const selectedOutfits = Array.from(outfitCheckboxes)
                .filter(checkbox => checkbox.checked)
                .map(checkbox => checkbox.dataset.outfitId);

            if (selectedOutfits.length === 0) {
                alert('Please select at least one outfit to favorite');
                return;
            }

            try {
                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
                if (!csrfToken) {
                    throw new Error('CSRF token not found');
                }

                for (const outfitId of selectedOutfits) {
                    const response = await fetch('/feedback', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify({
                            outfit_id: outfitId,
                            rating: 1
                        })
                    });

                    if (response.ok) {
                        const favoriteBtn = document.querySelector(`[data-outfit-id="${outfitId}"] .favorite-btn`);
                        if (favoriteBtn) {
                            favoriteBtn.classList.add('bg-yellow-400', 'text-yellow-600');
                            favoriteBtn.classList.remove('bg-white', 'text-gray-600');
                        }
                    }
                }

                // Deselect all checkboxes after operation
                outfitCheckboxes.forEach(checkbox => {
                    checkbox.checked = false;
                });
            } catch (error) {
                console.error('Error favoriting outfits:', error);
                alert('Error favoriting outfits. Please try again.');
            }
        });
    }

    if (deleteSelectedBtn) {
        deleteSelectedBtn.addEventListener('click', async () => {
            const selectedOutfits = Array.from(outfitCheckboxes)
                .filter(checkbox => checkbox.checked)
                .map(checkbox => checkbox.dataset.outfitId);

            if (selectedOutfits.length === 0) {
                alert('Please select at least one outfit to delete');
                return;
            }

            if (!confirm(`Are you sure you want to delete ${selectedOutfits.length} outfit(s)? This action cannot be undone.`)) {
                return;
            }

            try {
                const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
                if (!csrfToken) {
                    throw new Error('CSRF token not found');
                }

                for (const outfitId of selectedOutfits) {
                    const response = await fetch(`/delete-outfit/${outfitId}`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        }
                    });

                    if (response.ok) {
                        const outfitCard = document.querySelector(`[data-outfit-id="${outfitId}"]`);
                        if (outfitCard) {
                            outfitCard.remove();
                        }
                    }
                }

                // If no outfits left, reload the page
                const remainingOutfits = document.querySelectorAll('[data-outfit-id]');
                if (remainingOutfits.length === 0) {
                    window.location.reload();
                }
            } catch (error) {
                console.error('Error deleting outfits:', error);
                alert('Error deleting outfits. Please try again.');
            }
        });
    }
}); 

// === static/js/main.js  (2025-05-21) =======================================

// tiny DOM helpers ----------------------------------------------------------
const $  = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));
const csrf = () => $('meta[name="csrf-token"]')?.content;

// ---------------------------------------------------------------------------
// 1.  SINGLE-CARD ACTIONS  (star / trash icons)
// ---------------------------------------------------------------------------
window.toggleFavorite = async (id) => {
    const res = await fetch('/feedback', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() },
        body: JSON.stringify({ outfit_id: id, rating: 1 })
    });
    if (!res.ok) return alert('Failed to update favorite');

    const btn = $(`[data-outfit-id="${id}"] .favorite-btn`);
    btn?.classList.toggle('bg-yellow-400');
    btn?.classList.toggle('text-yellow-600');
    btn?.classList.toggle('bg-white');
    btn?.classList.toggle('text-gray-600');
};

// confirmDialog = false → skip the prompt (used for bulk delete)
window.deleteOutfit = async (id, confirmDialog = true) => {
    if (confirmDialog && !confirm('Delete this outfit forever?')) return;

    const res = await fetch(`/delete-outfit/${id}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }
    });
    if (!res.ok) return alert('Failed to delete outfit');

    $(`[data-outfit-id="${id}"]`)?.remove();
    if ($$('[data-outfit-id]').length === 0) location.reload();
};

// ---------------------------------------------------------------------------
// 2.  TOOLBAR BUTTONS  (select / deselect / favorite-selected / delete-selected)
// ---------------------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    const selAll = $('#select-all');
    const desAll = $('#deselect-all');
    const favSel = $('#favorite-selected');
    const delSel = $('#delete-selected');

    const boxes = () => $$('input.outfit-checkbox');

    selAll?.addEventListener('click', () => boxes().forEach(cb => cb.checked = true));
    desAll?.addEventListener('click', () => boxes().forEach(cb => cb.checked = false));

    favSel?.addEventListener('click', async () => {
        const ids = boxes().filter(cb => cb.checked).map(cb => cb.dataset.outfitId);
        if (!ids.length) return alert('Select at least one outfit first');

        for (const id of ids) await window.toggleFavorite(id);
        boxes().forEach(cb => cb.checked = false);
    });

    delSel?.addEventListener('click', async () => {
        const ids = boxes().filter(cb => cb.checked).map(cb => cb.dataset.outfitId);
        if (!ids.length) return alert('Select at least one outfit first');
        if (!confirm(`Delete ${ids.length} outfit(s)? This can’t be undone.`)) return;

        for (const id of ids) await window.deleteOutfit(id, /* confirmDialog */ false);
    });
});

// Store original notes when entering edit mode
let originalNotes = '';

// Handle edit mode toggle
document.addEventListener('DOMContentLoaded', function() {
    const toggleEditBtn = document.getElementById('toggle-edit');
    const existingNotes = document.getElementById('existing-notes');
    const saveExistingNotesBtn = document.getElementById('save-existing-notes');

    if (toggleEditBtn && existingNotes && saveExistingNotesBtn) {
        toggleEditBtn.addEventListener('click', () => {
            const isReadOnly = existingNotes.readOnly;
            if (isReadOnly) {
                // Entering edit mode - store original content
                originalNotes = existingNotes.value;
                existingNotes.readOnly = false;
                existingNotes.classList.remove('bg-gray-50');
                saveExistingNotesBtn.classList.remove('hidden');
                toggleEditBtn.textContent = 'Cancel Edit';
                toggleEditBtn.classList.remove('bg-gray-200');
                toggleEditBtn.classList.add('bg-red-200');
            } else {
                // Canceling edit - restore original content
                existingNotes.value = originalNotes;
                existingNotes.readOnly = true;
                existingNotes.classList.add('bg-gray-50');
                saveExistingNotesBtn.classList.add('hidden');
                toggleEditBtn.textContent = 'Edit Notes';
                toggleEditBtn.classList.remove('bg-red-200');
                toggleEditBtn.classList.add('bg-gray-200');
            }
        });

        // Handle saving changes to existing notes
        saveExistingNotesBtn.addEventListener('click', async () => {
            const notes = existingNotes.value;
            try {
                const response = await fetch('/update-ai-notes', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                    },
                    body: JSON.stringify({ notes })
                });
                if (response.ok) {
                    alert('Notes updated successfully!');
                    originalNotes = notes;
                    existingNotes.readOnly = true;
                    existingNotes.classList.add('bg-gray-50');
                    saveExistingNotesBtn.classList.add('hidden');
                    toggleEditBtn.textContent = 'Edit Notes';
                    toggleEditBtn.classList.remove('bg-red-200');
                    toggleEditBtn.classList.add('bg-gray-200');
                } else {
                    alert('Failed to update notes. Please try again.');
                }
            } catch (error) {
                console.error('Error updating notes:', error);
                alert('Failed to update notes. Please try again.');
            }
        });
    }

    // Handle adding new notes
    const notesForm = document.getElementById('notes-form');
    if (notesForm) {
        notesForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const newNotes = document.getElementById('new-notes').value;
            const existingNotesElem = document.getElementById('existing-notes');
            const existingNotesVal = existingNotesElem ? existingNotesElem.value : '';
            const combinedNotes = existingNotesVal ? `${existingNotesVal}\n${newNotes}` : newNotes;
            try {
                const response = await fetch('/update-ai-notes', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                    },
                    body: JSON.stringify({ notes: combinedNotes })
                });
                if (response.ok) {
                    alert('Note added successfully!');
                    if (existingNotesElem) existingNotesElem.value = combinedNotes;
                    document.getElementById('new-notes').value = '';
                } else {
                    alert('Failed to add note. Please try again.');
                }
            } catch (error) {
                console.error('Error adding note:', error);
                alert('Failed to add note. Please try again.');
            }
        });
    }

    // Handle description editing
    document.querySelectorAll('.edit-description-btn').forEach(button => {
        button.addEventListener('click', () => {
            const outfitId = button.dataset.outfitId;
            const descriptionDiv = document.getElementById(`outfit-description-${outfitId}`);
            const editForm = document.getElementById(`edit-form-${outfitId}`);
            if (descriptionDiv && editForm) {
                descriptionDiv.classList.add('hidden');
                editForm.classList.remove('hidden');
            }
        });
    });

    document.querySelectorAll('.cancel-edit-btn').forEach(button => {
        button.addEventListener('click', () => {
            const outfitId = button.dataset.outfitId;
            const descriptionDiv = document.getElementById(`outfit-description-${outfitId}`);
            const editForm = document.getElementById(`edit-form-${outfitId}`);
            if (descriptionDiv && editForm) {
                descriptionDiv.classList.remove('hidden');
                editForm.classList.add('hidden');
            }
        });
    });

    document.querySelectorAll('.save-description-btn').forEach(button => {
        button.addEventListener('click', async () => {
            const outfitId = button.dataset.outfitId;
            const descriptionDiv = document.getElementById(`outfit-description-${outfitId}`);
            const editForm = document.getElementById(`edit-form-${outfitId}`);
            const textarea = editForm ? editForm.querySelector('textarea') : null;
            const newDescription = textarea ? textarea.value : '';
            try {
                const response = await fetch(`/update-outfit-description/${outfitId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                    },
                    body: JSON.stringify({ description: newDescription })
                });
                if (response.ok) {
                    if (descriptionDiv) descriptionDiv.innerHTML = newDescription;
                    if (descriptionDiv) descriptionDiv.classList.remove('hidden');
                    if (editForm) editForm.classList.add('hidden');
                } else {
                    alert('Failed to update description. Please try again.');
                }
            } catch (error) {
                console.error('Error updating description:', error);
                alert('Failed to update description. Please try again.');
            }
        });
    });

    // Modal logic for full-size wardrobe images
    document.querySelectorAll('img.w-24.h-24.object-cover.rounded-lg').forEach(function(clickableImage) {
        clickableImage.style.cursor = 'pointer';
        clickableImage.addEventListener('click', function handleClick() {
            // Create the overlay element
            const overlay = document.createElement('div');
            overlay.style.position = 'fixed';
            overlay.style.top = '0';
            overlay.style.left = '0';
            overlay.style.width = '100%';
            overlay.style.height = '100%';
            overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
            overlay.style.zIndex = '1000';
            overlay.style.display = 'flex';
            overlay.style.justifyContent = 'center';
            overlay.style.alignItems = 'center';
            overlay.style.cursor = 'zoom-out';
            overlay.style.opacity = '0';
            overlay.style.transition = 'opacity 0.3s ease-in-out';

            // Create the full-size image element
            const fullSizeImage = document.createElement('img');
            fullSizeImage.src = clickableImage.src;
            fullSizeImage.style.maxWidth = '90%';
            fullSizeImage.style.maxHeight = '90%';
            fullSizeImage.style.objectFit = 'contain';
            fullSizeImage.style.borderRadius = '8px';

            // Prevent clicks on the image itself from closing the overlay immediately
            fullSizeImage.addEventListener('click', function(event) {
                event.stopPropagation();
            });

            overlay.appendChild(fullSizeImage);
            document.body.appendChild(overlay);

            // Fade in
            setTimeout(function() {
                overlay.style.opacity = '1';
            }, 10);

            overlay.addEventListener('click', function() {
                // Fade out
                overlay.style.opacity = '0';
                setTimeout(function() {
                    document.body.removeChild(overlay);
                }, 300); // Match the transition duration
            });
        });
    });
});

// Delete feedback function (global)
window.deleteFeedback = async function(feedbackId) {
    if (!confirm('Are you sure you want to delete this feedback?')) {
        return;
    }
    try {
        const response = await fetch(`/recommendation-feedback/${feedbackId}`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
            }
        });
        if (response.ok) {
            // Remove the feedback element from the DOM
            const feedbackElement = document.querySelector(`[data-feedback-id="${feedbackId}"]`).closest('.border');
            if (feedbackElement) feedbackElement.remove();
        } else {
            const error = await response.json();
            alert(error.error || 'Failed to delete feedback. Please try again.');
        }
    } catch (error) {
        console.error('Error deleting feedback:', error);
        alert('Failed to delete feedback. Please try again.');
    }
}; 
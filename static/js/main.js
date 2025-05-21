// Delete outfit function - defined globally
window.deleteOutfit = async (outfitId) => {
    console.log('Attempting to delete outfit:', outfitId);
    
    if (!confirm('Are you sure you want to delete this outfit? This action cannot be undone.')) {
        console.log('Delete cancelled by user');
        return;
    }

    try {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
        console.log('CSRF Token:', csrfToken ? 'Found' : 'Not found');
        
        if (!csrfToken) {
            throw new Error('CSRF token not found');
        }

        console.log('Sending delete request to:', `/delete-outfit/${outfitId}`);
        const response = await fetch(`/delete-outfit/${outfitId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        });

        console.log('Response status:', response.status);
        const data = await response.json();
        console.log('Response data:', data);

        if (response.ok) {
            console.log('Delete successful, removing outfit card');
            // Remove the outfit card from the DOM
            const outfitCard = document.querySelector(`[data-outfit-id="${outfitId}"]`);
            console.log('Found outfit card:', outfitCard ? 'Yes' : 'No');
            
            if (outfitCard) {
                outfitCard.remove();
                // If no outfits left, show the empty state
                const remainingOutfits = document.querySelectorAll('[data-outfit-id]');
                console.log('Remaining outfits:', remainingOutfits.length);
                if (remainingOutfits.length === 0) {
                    console.log('No outfits left, reloading page');
                    window.location.reload();
                }
            } else {
                console.log('Outfit card not found, reloading page');
                window.location.reload();
            }
        } else {
            throw new Error(data.error || 'Failed to delete outfit');
        }
    } catch (error) {
        console.error('Error deleting outfit:', error);
        alert(error.message || 'Error deleting outfit. Please try again.');
    }
};

document.addEventListener('DOMContentLoaded', () => {
    const clothingUpload = document.getElementById('clothing-upload');
    const preferencesForm = document.getElementById('preferences-form');
    const recommendationsContainer = document.getElementById('recommendations');
    const uploadPreview = document.getElementById('upload-preview');
    const previewContainer = document.getElementById('preview-container');
    const confirmUpload = document.getElementById('confirm-upload');

    let selectedFiles = [];

    // Handle clothing image selection
    clothingUpload.addEventListener('change', (e) => {
        const newFiles = Array.from(e.target.files);
        selectedFiles = [...selectedFiles, ...newFiles];
        
        if (selectedFiles.length > 0) {
            uploadPreview.classList.remove('hidden');
            
            // Only add previews for new files
            newFiles.forEach(file => {
                const reader = new FileReader();
                reader.onload = (e) => {
                    const preview = document.createElement('div');
                    preview.className = 'relative';
                    preview.dataset.filename = file.name;
                    preview.innerHTML = `
                        <img src="${e.target.result}" alt="Preview" class="w-full h-48 object-cover rounded-lg">
                        <button class="absolute top-2 right-2 bg-red-500 text-white rounded-full p-1 hover:bg-red-600" onclick="removeSelectedFile('${file.name}')">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </button>
                    `;
                    previewContainer.appendChild(preview);
                };
                reader.readAsDataURL(file);
            });
        }
    });

    // Remove selected file
    window.removeSelectedFile = (fileName) => {
        // Remove from selectedFiles array
        selectedFiles = selectedFiles.filter(file => file.name !== fileName);
        
        // Remove the preview element
        const preview = previewContainer.querySelector(`[data-filename="${fileName}"]`);
        if (preview) {
            preview.remove();
        }
        
        // Hide preview container if no files left
        if (selectedFiles.length === 0) {
            uploadPreview.classList.add('hidden');
        }
    };

    // Handle confirm upload
    if (confirmUpload) {
        confirmUpload.addEventListener('click', async () => {
            if (selectedFiles.length === 0) {
                alert('Please select at least one image to upload');
                return;
            }

            const formData = new FormData();
            for (let file of selectedFiles) {
                formData.append('image', file);
            }

            try {
                const response = await fetch('/upload', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content
                    },
                    body: formData
                });

                if (response.ok) {
                    const data = await response.json();
                    alert(data.message);
                    // Reset the form
                    clothingUpload.value = '';
                    selectedFiles = [];
                    uploadPreview.classList.add('hidden');
                    previewContainer.innerHTML = '';
                    // Reload the page to show new uploads
                    window.location.reload();
                } else {
                    const error = await response.json();
                    alert(error.error || 'Upload failed');
                }
            } catch (error) {
                console.error('Error uploading images:', error);
                alert('Error uploading images. Please try again.');
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
}); 
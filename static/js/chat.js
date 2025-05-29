document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const messageInput = document.getElementById('message-input');
    const chatMessages = document.getElementById('chat-messages');
    const chatHistory = document.getElementById('chat-history');
    const recommendationMode = document.getElementById('recommendation-mode');
    const modeLabel = document.getElementById('mode-label');
    let currentChatId = null;
    let feedbackMap = {};

    // Example questions pool
    const exampleQuestions = [
        "What should I wear for a casual dinner?",
        "Can you suggest an outfit for a job interview?",
        "What goes well with my blue shirt?",
        "Help me create a summer outfit",
        "What should I wear to a wedding?",
        "How can I style my black jeans?",
        "What outfit is good for a rainy day?",
        "Suggest something for a first date",
        "What can I wear to look taller?",
        "How do I dress for a business meeting?",
        "What goes well with white sneakers?",
        "Can you help me pick an outfit for a party?",
        "What should I wear for a winter walk?",
        "How do I style a denim jacket?",
        "What is a good outfit for brunch?",
        "How can I layer clothes for fall?",
        "What should I wear to a concert?",
        "Suggest a comfy travel outfit",
        "What can I wear for a beach day?",
        "How do I dress for a hot summer day?",
        "What should I wear for a workout?",
        "How do I style a floral dress?",
        "What goes well with a red skirt?",
        "What should I wear for a family gathering?",
        "How do I dress up casual clothes?",
        "What is a good outfit for hiking?",
        "How do I style boots in spring?",
        "What should I wear for a movie night?",
        "How do I make my outfit look more formal?",
        "What can I wear for a cozy night in?"
    ];

    // Update mode label based on toggle state
    function updateModeLabel() {
        if (recommendationMode.checked) {
            modeLabel.textContent = 'Recommend from my wardrobe only';
            modeLabel.classList.remove('text-gray-700');
            modeLabel.classList.add('text-indigo-600', 'font-semibold');
        } else {
            modeLabel.textContent = 'Recommend from all clothes';
            modeLabel.classList.remove('text-indigo-600', 'font-semibold');
            modeLabel.classList.add('text-gray-700');
        }
    }

    // Add toggle switch event listener
    recommendationMode.addEventListener('change', updateModeLabel);

    // Function to show welcome messages
    function showWelcomeMessages() {
        addMessage('AI', 'Hi! I\'m your AI Fashion Assistant. I can help you create perfect outfits using your uploaded clothes. You can ask me things like:', true);
        // Pick 4 random questions
        const shuffled = exampleQuestions.sort(() => 0.5 - Math.random());
        const selected = shuffled.slice(0, 4);
        const listHtml = '<ul class="list-disc pl-6 space-y-1">' + selected.map(q => `<li>${q}</li>`).join('') + '</ul>';
        addMessage('AI', listHtml, [], false);
    }

    // Show welcome messages on initial load
    showWelcomeMessages();

    // Load chat history
    loadChatHistory(1);

    // Fetch all feedback for the user
    async function fetchFeedback() {
        try {
            const response = await fetch('/chat-feedback');
            const data = await response.json();
            feedbackMap = {};
            data.feedback.forEach(entry => {
                // Key by recommendation + question
                feedbackMap[entry.recommendation + '||' + entry.question] = entry.feedback;
            });
        } catch (error) {
            console.error('Error fetching feedback:', error);
        }
    }

    // On page load, fetch feedback
    fetchFeedback();

    // Handle form submission
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = messageInput.value.trim();
        if (!message) return;

        // Add user message to chat
        addMessage('You', message);
        messageInput.value = '';

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                },
                body: JSON.stringify({ 
                    message,
                    chat_id: currentChatId,  // Include current chat ID if it exists
                    wardrobe_only: recommendationMode.checked  // Include recommendation mode
                })
            });

            const data = await response.json();
            
            if (response.ok) {
                // Update current chat ID
                currentChatId = data.chat_id;
                
                // Add AI response to chat
                addMessage('AI', data.response, data.image_urls, true);
                
                // Update chat history
                loadChatHistory();
            } else {
                addMessage('AI', 'Sorry, I encountered an error. Please try again.', true);
            }
        } catch (error) {
            console.error('Error:', error);
            addMessage('AI', 'Sorry, I encountered an error. Please try again.', true);
        }
    });

    // Function to add a message to the chat
    function addMessage(sender, text, imageUrls = [], isRecommendation = false, question = null) {
        const messagesDiv = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `flex ${sender === 'You' ? 'justify-end' : 'justify-start'}`;
        
        let messageContent = `
            <div class="max-w-[70%] ${sender === 'You' ? 'bg-indigo-600 text-white' : 'bg-gray-100 text-gray-800'} rounded-lg p-3">
                <p class="text-sm">${text}</p>
        `;
        
        // Add images if present
        if (imageUrls && imageUrls.length > 0) {
            messageContent += '<div class="mt-2 flex flex-wrap gap-2">';
            imageUrls.forEach(url => {
                messageContent += `
                    <img src="${url}" alt="Recommended item" class="w-20 h-20 object-cover rounded-lg">
                `;
            });
            messageContent += '</div>';
        }
        
        // Add feedback buttons for AI recommendations
        if (isRecommendation && sender === 'AI') {
            // Get the user's question from the previous message if not provided
            let msgQuestion = question;
            if (!msgQuestion) {
                const messages = chatMessages.querySelectorAll('.flex');
                msgQuestion = Array.from(messages)
                    .reverse()
                    .find(msg => msg.querySelector('.bg-indigo-600'))?.querySelector('.text-sm')?.textContent || '';
            }
            // Track feedback state
            let currentFeedback = feedbackMap[text + '||' + msgQuestion] || null;
            messageContent += `
                <div class="mt-2 flex justify-end space-x-2">
                    <button class="feedback-btn px-2 py-1 text-xs rounded-md bg-gray-200 text-gray-700 hover:bg-gray-300" data-feedback="like" data-recommendation="${text}" data-question="${msgQuestion}">
                        👍 Like
                    </button>
                    <button class="feedback-btn px-2 py-1 text-xs rounded-md bg-gray-200 text-gray-700 hover:bg-gray-300" data-feedback="dislike" data-recommendation="${text}" data-question="${msgQuestion}">
                        👎 Dislike
                    </button>
                </div>
            `;
        }
        
        messageContent += '</div>';
        messageDiv.innerHTML = messageContent;
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
        
        // Add event listeners to feedback buttons if they exist
        if (isRecommendation && sender === 'AI') {
            let msgQuestion = question;
            if (!msgQuestion) {
                const messages = chatMessages.querySelectorAll('.flex');
                msgQuestion = Array.from(messages)
                    .reverse()
                    .find(msg => msg.querySelector('.bg-indigo-600'))?.querySelector('.text-sm')?.textContent || '';
            }
            let selectedFeedback = feedbackMap[text + '||' + msgQuestion] || null;
            const likeBtn = messageDiv.querySelector('button[data-feedback="like"]');
            const dislikeBtn = messageDiv.querySelector('button[data-feedback="dislike"]');
            const feedbackBtns = [likeBtn, dislikeBtn];
            // Set initial button state
            if (selectedFeedback === 'like') likeBtn.classList.add('bg-green-200');
            if (selectedFeedback === 'dislike') dislikeBtn.classList.add('bg-red-200');
            feedbackBtns.forEach(button => {
                button.addEventListener('click', async () => {
                    const feedback = button.dataset.feedback;
                    const recommendation = button.dataset.recommendation;
                    const question = button.dataset.question;
                    // Toggle logic
                    let newFeedback;
                    if (selectedFeedback === feedback) {
                        newFeedback = 'remove';
                    } else {
                        newFeedback = feedback;
                    }
                    try {
                        const response = await fetch('/recommendation-feedback', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                            },
                            body: JSON.stringify({
                                recommendation: recommendation,
                                feedback: newFeedback,
                                question: question,
                                context: {
                                    timestamp: new Date().toISOString()
                                }
                            })
                        });
                        if (response.ok) {
                            if (newFeedback === 'remove') {
                                selectedFeedback = null;
                                feedbackMap[recommendation + '||' + question] = null;
                                feedbackBtns.forEach(btn => {
                                    btn.classList.remove('bg-green-200', 'bg-red-200', 'opacity-50');
                                    btn.disabled = false;
                                });
                            } else {
                                selectedFeedback = feedback;
                                feedbackMap[recommendation + '||' + question] = feedback;
                                feedbackBtns.forEach(btn => {
                                    btn.classList.remove('bg-green-200', 'bg-red-200', 'opacity-50');
                                    btn.disabled = false;
                                });
                                button.classList.add(feedback === 'like' ? 'bg-green-200' : 'bg-red-200');
                            }
                        } else {
                            const errorData = await response.json();
                            console.error('Error response:', errorData);
                            alert('Failed to save feedback. Please try again.');
                        }
                    } catch (error) {
                        console.error('Error saving feedback:', error);
                        alert('Failed to save feedback. Please try again.');
                    }
                });
            });
        }
    }

    // Function to load chat history
    async function loadChatHistory(page = 1) {
        try {
            const response = await fetch(`/chat-history?page=${page}`);
            const data = await response.json();
            
            chatHistory.innerHTML = '';
            data.chats.forEach(chat => {
                const chatItem = document.createElement('div');
                chatItem.className = `p-3 rounded-lg hover:bg-gray-100 cursor-pointer ${chat.id === currentChatId ? 'bg-gray-100' : ''}`;
                chatItem.innerHTML = `
                    <div class="flex justify-between items-start">
                        <div class="flex-1">
                            <div class="text-sm font-medium text-gray-900">${chat.preview}</div>
                            <div class="text-xs text-gray-500">${new Date(chat.timestamp).toLocaleString()}</div>
                        </div>
                        <button class="delete-chat ml-2 p-1 text-gray-400 hover:text-red-500 rounded-full hover:bg-gray-200" data-chat-id="${chat.id}">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                        </button>
                    </div>
                `;
                // Add click handler for the chat item
                chatItem.querySelector('.flex-1').addEventListener('click', () => loadChat(chat.id));
                // Add click handler for the delete button
                chatItem.querySelector('.delete-chat').addEventListener('click', async (e) => {
                    e.stopPropagation();
                    if (confirm('Are you sure you want to delete this chat?')) {
                        try {
                            const response = await fetch(`/chat/${chat.id}`, {
                                method: 'DELETE',
                                headers: {
                                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                                }
                            });
                            if (response.ok) {
                                if (chat.id === currentChatId) {
                                    chatMessages.innerHTML = '';
                                    currentChatId = null;
                                }
                                loadChatHistory(page);
                            } else {
                                alert('Failed to delete chat. Please try again.');
                            }
                        } catch (error) {
                            console.error('Error deleting chat:', error);
                            alert('Failed to delete chat. Please try again.');
                        }
                    }
                });
                chatHistory.appendChild(chatItem);
            });
            // Pagination controls
            const paginationDiv = document.createElement('div');
            paginationDiv.className = 'flex justify-between mt-4';
            if (data.has_prev) {
                const prevBtn = document.createElement('button');
                prevBtn.textContent = 'Previous';
                prevBtn.className = 'px-3 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300';
                prevBtn.addEventListener('click', () => loadChatHistory(data.page - 1));
                paginationDiv.appendChild(prevBtn);
            } else {
                const spacer = document.createElement('div');
                paginationDiv.appendChild(spacer);
            }
            const pageInfo = document.createElement('span');
            pageInfo.textContent = `Page ${data.page} of ${data.pages}`;
            pageInfo.className = 'text-xs text-gray-500 self-center';
            paginationDiv.appendChild(pageInfo);
            if (data.has_next) {
                const nextBtn = document.createElement('button');
                nextBtn.textContent = 'Next';
                nextBtn.className = 'px-3 py-1 bg-gray-200 text-gray-700 rounded hover:bg-gray-300';
                nextBtn.addEventListener('click', () => loadChatHistory(data.page + 1));
                paginationDiv.appendChild(nextBtn);
            } else {
                const spacer = document.createElement('div');
                paginationDiv.appendChild(spacer);
            }
            chatHistory.appendChild(paginationDiv);
        } catch (error) {
            console.error('Error loading chat history:', error);
        }
    }

    // Function to load a specific chat
    async function loadChat(chatId) {
        try {
            await fetchFeedback();
            const response = await fetch(`/chat/${chatId}`);
            const data = await response.json();
            
            // Clear current chat
            chatMessages.innerHTML = '';
            
            // Add messages from the loaded chat
            data.messages.forEach(message => {
                addMessage(message.sender, message.text, message.image_urls, message.sender === 'AI', message.sender === 'AI' ? message.question : null);
            });
            
            currentChatId = chatId;
            
            // Update chat history to highlight current chat
            loadChatHistory();
        } catch (error) {
            console.error('Error loading chat:', error);
        }
    }

    // Modal logic for full-size images in chat
    document.getElementById('chat-messages').addEventListener('click', function(e) {
        if (e.target.tagName === 'IMG') {
            const imageUrl = e.target.src;
            const overlay = document.createElement('div');
            overlay.style.position = 'fixed';
            overlay.style.top = '0';
            overlay.style.left = '0';
            overlay.style.width = '100%';
            overlay.style.height = '100%';
            overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
            overlay.style.display = 'flex';
            overlay.style.justifyContent = 'center';
            overlay.style.alignItems = 'center';
            overlay.style.zIndex = '1000';
            overlay.style.cursor = 'pointer';

            const fullImg = document.createElement('img');
            fullImg.src = imageUrl;
            fullImg.style.maxWidth = '90%';
            fullImg.style.maxHeight = '90%';
            fullImg.style.objectFit = 'contain';

            overlay.appendChild(fullImg);
            document.body.appendChild(overlay);

            e.target.style.visibility = 'hidden';

            overlay.addEventListener('click', function() {
                document.body.removeChild(overlay);
                e.target.style.visibility = 'visible';
            });
        }
    });

    // Add event listener for New Chat button
    document.getElementById('new-chat-btn').addEventListener('click', () => {
        chatMessages.innerHTML = '';
        currentChatId = null;
        loadChatHistory();
        showWelcomeMessages();
    });
}); 
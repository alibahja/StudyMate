// ==========================================
// DOM Elements
// ==========================================

const fileInput = document.getElementById('fileInput');
const uploadZone = document.getElementById('uploadZone');
const fileInfo = document.getElementById('fileInfo');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const removeFileBtn = document.getElementById('removeFileBtn');
const uploadBtn = document.getElementById('uploadBtn');
const userQuery = document.getElementById('userQuery');
const uploadSection = document.getElementById('uploadSection');
const resultsSection = document.getElementById('resultsSection');
const uploadProgress = document.getElementById('uploadProgress');
const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const threadIdDisplay = document.getElementById('threadIdDisplay');
const downloadBtn = document.getElementById('downloadBtn');
const newChatBtn = document.getElementById('newChatBtn');

// Tab elements
const tabBtns = document.querySelectorAll('.tab-btn');
const tabPanes = {
    explanation: document.querySelector('#tab-explanation .content-body'),
    summary: document.querySelector('#tab-summary .content-body'),
    mcqs: document.querySelector('#tab-mcqs .content-body'),
    subjective: document.querySelector('#tab-subjective .content-body'),
    solutions: document.querySelector('#tab-solutions .content-body')
};

// Stats elements
const wordCount = document.getElementById('wordCount');
const llmCalls = document.getElementById('llmCalls');
const processingTime = document.getElementById('processingTime');

// ==========================================
// State
// ==========================================

let selectedFile = null;
let currentThreadId = null;
let currentData = null;
let startTime = null;

// ==========================================
// File Upload Handling
// ==========================================

uploadZone.addEventListener('click', () => fileInput.click());

uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('dragover');
});

uploadZone.addEventListener('dragleave', () => {
    uploadZone.classList.remove('dragover');
});

uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFileSelect(files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
    }
});

function handleFileSelect(file) {
    const allowedExtensions = ['.pdf', '.docx'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!allowedExtensions.includes(ext)) {
        alert('Please upload a PDF or DOCX file.');
        fileInput.value = '';
        return;
    }
    
    selectedFile = file;
    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);
    fileInfo.style.display = 'flex';
    uploadZone.style.display = 'none';
    uploadBtn.disabled = false;
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

removeFileBtn.addEventListener('click', () => {
    selectedFile = null;
    fileInfo.style.display = 'none';
    uploadZone.style.display = 'block';
    uploadBtn.disabled = true;
    fileInput.value = '';
});

// ==========================================
// Upload Handler
// ==========================================

uploadBtn.addEventListener('click', uploadFile);

async function uploadFile() {
    if (!selectedFile) return;
    
    // Prepare UI
    uploadBtn.disabled = true;
    uploadBtn.innerHTML = 'Processing…';
    uploadProgress.style.display = 'block';
    progressFill.style.width = '0%';
    progressText.textContent = 'Uploading file...';
    startTime = Date.now();
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('user_query', userQuery.value);
    if (currentThreadId) {
        formData.append('thread_id', currentThreadId);
    }
    
    try {
        // Progress simulation
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 8;
            if (progress > 90) progress = 90;
            progressFill.style.width = progress + '%';
            if (progress < 30) progressText.textContent = 'Uploading file...';
            else if (progress < 60) progressText.textContent = 'Extracting text from document...';
            else progressText.textContent = 'Generating study materials with AI agents...';
        }, 300);
        
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        clearInterval(progressInterval);
        progressFill.style.width = '100%';
        progressText.textContent = 'Complete!';
        
        const data = await response.json();
        
        if (data.success) {
            currentThreadId = data.thread_id;
            currentData = data;
            displayResults(data);
        } else {
            throw new Error(data.error || 'Unknown error occurred');
        }
        
    } catch (error) {
        console.error('Upload error:', error);
        progressText.textContent = 'Error: ' + error.message;
        alert('Error processing your file: ' + error.message);
    } finally {
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = 'Generate study materials';
        setTimeout(() => {
            uploadProgress.style.display = 'none';
        }, 1000);
    }
}

// ==========================================
// Results Display
// ==========================================

function displayResults(data) {
    // Show results section
    uploadSection.style.display = 'none';
    resultsSection.style.display = 'block';
    
    // Set thread ID
    threadIdDisplay.textContent = `Thread: ${data.thread_id}`;
    
    // Populate content
    const contentMap = {
        explanation: data.explanation || 'No explanation generated.',
        summary: data.summary || 'No summary generated.',
        mcqs: formatMCQs(data.mcqs || 'No MCQs generated.'),
        subjective: data.subjective_questions || 'No subjective questions generated.',
        solutions: data.solutions || 'No solutions generated.'
    };
    
    tabPanes.explanation.innerHTML = formatContent(contentMap.explanation);
    tabPanes.summary.innerHTML = formatContent(contentMap.summary);
    tabPanes.mcqs.innerHTML = formatContent(contentMap.mcqs);
    tabPanes.subjective.innerHTML = formatContent(contentMap.subjective);
    tabPanes.solutions.innerHTML = formatContent(contentMap.solutions);
    
    // Update stats
    wordCount.textContent = data.word_count || '?';
    llmCalls.textContent = data.llm_calls || 0;
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    processingTime.textContent = elapsed;
    
    // Enable download
    downloadBtn.style.display = 'inline-flex';
    downloadBtn.dataset.threadId = data.thread_id;
    
    // Scroll to results
    resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function formatContent(text) {
    if (!text) return '<p>No content available.</p>';
    
    // Convert markdown-like formatting
    let html = text;
    
    // Headers (##)
    html = html.replace(/^## (.*$)/gm, '<h4>$1</h4>');
    html = html.replace(/^### (.*$)/gm, '<h5>$1</h5>');
    
    // Bold
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Italic
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    // Bullet points
    html = html.replace(/^[-*] (.*$)/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');
    
    // Numbered lists
    html = html.replace(/^\d+\. (.*$)/gm, '<li>$1</li>');
    
    // Line breaks
    html = html.replace(/\n/g, '<br>');
    
    // Clean up multiple breaks
    html = html.replace(/(<br>){3,}/g, '<br><br>');
    
    return html;
}

// At the top of script.js, add:
async function checkAuth() {
    try {
        const response = await fetch('/api/check-auth');
        const data = await response.json();
        if (!data.authenticated) {
            window.location.href = '/login';
        }
        return data;
    } catch (error) {
        window.location.href = '/login';
    }
}

function formatMCQs(text) {
    if (!text || text === 'No MCQs generated.') return text;
    
    let html = '';
    const lines = text.split('\n');
    let currentQuestion = '';
    
    for (let line of lines) {
        line = line.trim();
        if (!line) continue;
        
        // Question (Q1, Q2, etc.)
        if (line.match(/^Q\d+[:.]/i)) {
            if (currentQuestion) {
                html += '<div class="question">' + currentQuestion + '</div>';
            }
            currentQuestion = line;
        } 
        // Options (A), B), etc.)
        else if (line.match(/^[A-D]\)/)) {
            html += '<div style="padding-left: 20px; margin: 2px 0;">' + line + '</div>';
        }
        // Answer
        else if (line.includes('Answer:')) {
            html += '<div class="answer">' + line + '</div>';
            currentQuestion = '';
        }
        // Continue question
        else if (currentQuestion) {
            currentQuestion += ' ' + line;
        }
        // Regular line
        else {
            html += '<p>' + line + '</p>';
        }
    }
    
    if (currentQuestion) {
        html += '<div class="question">' + currentQuestion + '</div>';
    }
    
    return html || text;
}

// ==========================================
// Tab Switching
// ==========================================

tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        // Remove active from all tabs
        tabBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        
        // Show corresponding pane
        const tabId = btn.dataset.tab;
        document.querySelectorAll('.tab-pane').forEach(pane => {
            pane.classList.remove('active');
        });
        document.getElementById('tab-' + tabId).classList.add('active');
    });
});

// ==========================================
// Download PDF
// ==========================================

downloadBtn.addEventListener('click', async () => {
    const threadId = downloadBtn.dataset.threadId;
    if (!threadId) return;
    
    window.open(`/api/download/${threadId}`, '_blank');
});

// ==========================================
// New Session
// ==========================================

newChatBtn.addEventListener('click', () => {
    // Reset everything
    selectedFile = null;
    currentThreadId = null;
    currentData = null;
    fileInfo.style.display = 'none';
    uploadZone.style.display = 'block';
    uploadBtn.disabled = true;
    userQuery.value = '';
    fileInput.value = '';
    resultsSection.style.display = 'none';
    uploadSection.style.display = 'flex';
    uploadProgress.style.display = 'none';
    progressFill.style.width = '0%';
    downloadBtn.style.display = 'none';
    
    // Reset tabs
    tabBtns.forEach(b => b.classList.remove('active'));
    document.querySelector('.tab-btn[data-tab="explanation"]').classList.add('active');
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));
    document.getElementById('tab-explanation').classList.add('active');
    
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
});

// ==========================================
// Keyboard Shortcuts
// ==========================================

document.addEventListener('keydown', (e) => {
    // Ctrl+Enter to upload
    if (e.ctrlKey && e.key === 'Enter' && !uploadBtn.disabled) {
        uploadBtn.click();
    }
});

// ==========================================
// Init
// ==========================================

console.log('StudyMate loaded');
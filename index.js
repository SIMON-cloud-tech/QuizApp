// ══════════════════════════════════════════
//  DB SETUP
// ══════════════════════════════════════════

// Database configuration
const DB_NAME = "quizapp", DB_VERSION = 2;
let db; // Global database instance

/**
 * Initialize IndexedDB database connection
 * @returns {Promise<IDBDatabase>} Database instance
 */
function openDB() {
  return new Promise((res, rej) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = e => {
      const d = e.target.result;
      // Create object stores if they don't exist
      if (!d.objectStoreNames.contains("books"))      d.createObjectStore("books",      { keyPath: "id" });
      if (!d.objectStoreNames.contains("summaries"))  d.createObjectStore("summaries",  { keyPath: "bookId" });
      if (!d.objectStoreNames.contains("quizzes"))    d.createObjectStore("quizzes",    { keyPath: "bookId" });
      if (!d.objectStoreNames.contains("taskCounts")) d.createObjectStore("taskCounts", { keyPath: "bookId" });
    };
    req.onsuccess = e => { db = e.target.result; res(db); };
    req.onerror   = () => rej(req.error);
  });
}

/**
 * Store an object in IndexedDB
 * @param {string} store - Object store name
 * @param {Object} obj - Object to store
 * @returns {Promise<void>}
 */
function dbSet(store, obj) {
  return new Promise((r, e) => {
    const t = db.transaction(store, "readwrite").objectStore(store).put(obj);
    t.onsuccess = () => r();
    t.onerror   = () => e(t.error);
  });
}

/**
 * Retrieve an object from IndexedDB
 * @param {string} store - Object store name
 * @param {string} key - Primary key
 * @returns {Promise<Object>} Retrieved object
 */
function dbGet(store, key) {
  return new Promise((r, e) => {
    const t = db.transaction(store).objectStore(store).get(key);
    t.onsuccess = () => r(t.result);
    t.onerror   = () => e(t.error);
  });
}

/**
 * Delete an object from IndexedDB
 * @param {string} store - Object store name
 * @param {string} key - Primary key
 * @returns {Promise<void>}
 */
function dbDel(store, key) {
  return new Promise((r, e) => {
    const t = db.transaction(store, "readwrite").objectStore(store).delete(key);
    t.onsuccess = () => r();
    t.onerror   = () => e(t.error);
  });
}

/**
 * Retrieve all objects from an IndexedDB store
 * @param {string} store - Object store name
 * @returns {Promise<Array>} Array of all objects
 */
function dbAll(store) {
  return new Promise((r, e) => {
    const t = db.transaction(store).objectStore(store).getAll();
    t.onsuccess = () => r(t.result);
    t.onerror   = () => e(t.error);
  });
}


// ══════════════════════════════════════════
//  THEME
// ══════════════════════════════════════════

/**
 * Toggle between light and dark theme
 */
function toggleTheme() {
  const html = document.documentElement;
  html.dataset.theme = html.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("theme", html.dataset.theme);
}

/**
 * Load saved theme preference from localStorage
 */
function loadTheme() {
  const saved = localStorage.getItem("theme");
  if (saved) document.documentElement.dataset.theme = saved;
}


// ══════════════════════════════════════════
//  NAVBAR
// ══════════════════════════════════════════

// Mobile navigation toggle
document.getElementById("hamburger").addEventListener("click", () => {
  document.getElementById("navLinks").classList.toggle("open");
});


// ══════════════════════════════════════════
//  PAGE ROUTING
// ══════════════════════════════════════════

/**
 * Navigate between pages and render content
 * @param {string} page - Page name ('main', 'quizzes', 'summaries')
 */
function showPage(page) {
  // Hide all pages and show selected page
  ["main", "quizzes", "summaries"].forEach(p => {
    document.getElementById(`page-${p}`).style.display = p === page ? "block" : "none";
  });
  // Render page-specific content
  if (page === "quizzes")   renderAllQuizzes();
  if (page === "summaries") renderAllSummaries();
  // Close mobile navigation
  document.getElementById("navLinks").classList.remove("open");
}

/**
 * Smooth scroll to element by ID
 * @param {string} id - Element ID to scroll to
 */
function scrollTo(id) {
  setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }), 50);
}


// ══════════════════════════════════════════
//  UPLOAD
// ══════════════════════════════════════════

// File upload elements
const uploadArea   = document.getElementById("uploadArea");
const fileInput    = document.getElementById("fileInput");
const uploadStatus = document.getElementById("uploadStatus");

// Drag and drop event handlers
uploadArea.addEventListener("dragover",  e  => { e.preventDefault(); uploadArea.classList.add("dragover"); });
uploadArea.addEventListener("dragleave", () => uploadArea.classList.remove("dragover"));
uploadArea.addEventListener("drop",      e  => { e.preventDefault(); uploadArea.classList.remove("dragover"); handleFile(e.dataTransfer.files[0]); });
uploadArea.addEventListener("click",     () => fileInput.click());
fileInput.addEventListener("change",     () => handleFile(fileInput.files[0]));

/**
 * Handle uploaded PDF file
 * @param {File} file - PDF file to process
 */
async function handleFile(file) {
  console.log("handleFile called with:", file);
  
  // Validate file type
  if (!file || file.type !== "application/pdf") {
    console.log("Invalid file type:", file?.type);
    uploadStatus.textContent = "Only PDF files are accepted.";
    return;
  }

  console.log("File validation passed");
  uploadStatus.textContent = "Reading file...";
  const base64 = await fileToBase64(file);
  const id     = `book_${Date.now()}`;
  const name   = file.name.replace(".pdf", "");
  
  console.log("File converted to base64, length:", base64.length);

  // Save book immediately so the card appears
  const book = { id, name, base64, description: "Fetching description...", cover: null };
  console.log("Saving book to DB:", book);
  await dbSet("books", book);
  console.log("Book saved, rendering books");
  renderBooks();
  uploadStatus.textContent = "Book saved. Generating description...";

  // Fetch description from server
  try {
    console.log("Fetching description from server...");
    const res        = await fetch("http://localhost:5000/describe", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ base64 })
    });
    console.log("Server response status:", res.status);
    const data       = await res.json();
    console.log("Server response data:", data);
    book.description = data.description;
    await dbSet("books", book);
    renderBooks();
    uploadStatus.textContent = "Fetching cover...";
  } catch (error) {
    console.error("Error fetching description:", error);
    book.description = "Description unavailable — is the server running?";
    await dbSet("books", book);
    renderBooks();
    uploadStatus.textContent = "Fetching cover...";
  }

  // Fetch cover image from server
  try {
    const coverRes  = await fetch("http://localhost:5000/cover", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ base64 })
    });
    const coverData = await coverRes.json();
    book.cover      = coverData.cover;
    await dbSet("books", book);
    renderBooks();
    uploadStatus.textContent = "Book ready.";
  } catch {
    // placeholder image stays, not a critical failure
    uploadStatus.textContent = "Book ready (cover unavailable).";
  }
}

/**
 * Convert file to base64 string
 * @param {File} file - File to convert
 * @returns {Promise<string>} Base64 encoded string
 */
function fileToBase64(file) {
  return new Promise((res, rej) => {
    const r   = new FileReader();
    r.onload  = () => res(r.result.split(",")[1]);
    r.onerror = () => rej();
    r.readAsDataURL(file);
  });
}


// ══════════════════════════════════════════
//  QA CARD RENDERER
// ══════════════════════════════════════════

/**
 * Render Q&A text as individual cards
 * @param {string} text - Q&A text to format
 * @returns {string} HTML string with formatted cards
 */
function renderQACards(text) {
  if (!text) return `<p class="muted">Nothing to display.</p>`;

  // Split on lines starting with Q1. A1. or just 1.
  const items = text
    .split(/\n(?=(?:Q|A)?\d+[\.\)])/i)
    .map(s => s.trim())
    .filter(Boolean);

  if (items.length === 0) {
    // Fallback: split by newline
    return text.split("\n").filter(Boolean)
      .map(line => `<div class="qa-card">${line}</div>`)
      .join("");
  }

  return items.map(item => `<div class="qa-card">${item}</div>`).join("");
}


// ══════════════════════════════════════════
//  QUEUE MANAGER
// ══════════════════════════════════════════

// Task queue management
const taskQueue = [];
let activeTask  = null; // Currently running task

/**
 * Add a task to the processing queue
 * @param {string} bookId - Book identifier
 * @param {string} task - Task type ('quiz' or 'summary')
 */
async function enqueue(bookId, task) {
  // Check processing limit (max 3 per task per book)
  const record = await dbGet("taskCounts", bookId) || { bookId, quiz: 0, summary: 0 };
  if (record[task] >= 3) {
    alert(`This book has already been processed for ${task} 3 times. Limit reached.`);
    return;
  }

  // Prevent duplicate queuing
  const alreadyQueued = taskQueue.some(t => t.bookId === bookId && t.task === task);
  const isActive      = activeTask && activeTask.bookId === bookId && activeTask.task === task;
  if (alreadyQueued || isActive) {
    alert(`${task} for this book is already running or queued.`);
    return;
  }

  taskQueue.push({ bookId, task });
  updateCardBadge(bookId);
  processQueue();
}

/**
 * Process the task queue (run one task at a time)
 */
async function processQueue() {
  if (activeTask || taskQueue.length === 0) return;

  activeTask = taskQueue.shift();
  const { bookId, task } = activeTask;
  updateCardBadge(bookId);

  const book = await dbGet("books", bookId);
  if (!book) { activeTask = null; processQueue(); return; }

  let success = false;
  if (task === "summary") success = await runSummary(book);
  if (task === "quiz")    success = await runQuiz(book);

  // Only increment count on success — failed calls don't count
  if (success) {
    const record  = await dbGet("taskCounts", bookId) || { bookId, quiz: 0, summary: 0 };
    record[task] += 1;
    await dbSet("taskCounts", record);
  }

  activeTask = null;
  updateCardBadge(bookId);
  processQueue(); // pick next from queue
}

/**
 * Update the queue badge on book cards
 * @param {string} bookId - Book identifier
 */
function updateCardBadge(bookId) {
  const card = document.querySelector(`[data-book-id="${bookId}"]`);
  if (!card) return;

  let badge      = card.querySelector(".queue-badge");
  const pending  = taskQueue.filter(t => t.bookId === bookId).length;
  const isActive = activeTask && activeTask.bookId === bookId;

  if (isActive) {
    if (!badge) { badge = document.createElement("span"); badge.className = "queue-badge"; card.appendChild(badge); }
    badge.textContent = `Running: ${activeTask.task}`;
  } else if (pending > 0) {
    if (!badge) { badge = document.createElement("span"); badge.className = "queue-badge"; card.appendChild(badge); }
    badge.textContent = `Queued: ${pending}`;
  } else {
    badge?.remove();
  }
}


// ══════════════════════════════════════════
//  RUN SUMMARY
// ══════════════════════════════════════════

/**
 * Generate summary for a book
 * @param {Object} book - Book object with id, name, and base64
 * @returns {Promise<boolean>} Success status
 */
async function runSummary(book) {
  document.getElementById("summaryOutput").style.display = "block";
  const box = document.getElementById("summaryText");
  box.textContent = "Generating summary...";
  scrollTo("summaryOutput");

  try {
    const res  = await fetch("http://localhost:5000/summarize", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ bookId: book.id, base64: book.base64 })
    });
    const data = await res.json();
    box.textContent = data.summary;
    await dbSet("summaries", {
      bookId:    book.id,
      bookName:  book.name,
      summary:   data.summary,
      createdAt: Date.now()
    });
    return true;
  } catch {
    box.textContent = "Error generating summary. Is the server running?";
    return false;
  }
}


// ══════════════════════════════════════════
//  RUN QUIZ
// ══════════════════════════════════════════

/**
 * Generate quiz questions for a book
 * @param {Object} book - Book object with id, name, and base64
 * @returns {Promise<boolean>} Success status
 */
async function runQuiz(book) {
  document.getElementById("quizOutput").style.display = "block";
  const qBox = document.getElementById("questionsText");
  const aBox = document.getElementById("answersText");
  qBox.innerHTML = `<p class="muted">Generating questions...</p>`;
  aBox.innerHTML = `<p class="muted">Answers appear 3 minutes after questions are ready.</p>`;
  scrollTo("quizOutput");

  try {
    const res  = await fetch("http://localhost:5000/quiz", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ bookId: book.id, base64: book.base64 })
    });
    const data = await res.json();

    // Render each question as its own card
    qBox.innerHTML = renderQACards(data.questions);

    await dbSet("quizzes", {
      bookId:    book.id,
      bookName:  book.name,
      questions: data.questions,
      answers:   data.answers,
      createdAt: Date.now()
    });

    // Answers unlock after 3 minutes
    setTimeout(() => {
      aBox.innerHTML = renderQACards(data.answers);
    }, 3 * 60 * 1000);

    return true;
  } catch {
    qBox.innerHTML = `<p class="muted">Error generating quiz. Is the server running?</p>`;
    return false;
  }
}


// ══════════════════════════════════════════
//  RENDER BOOKS
// ══════════════════════════════════════════

/**
 * Render all books in the grid
 */
async function renderBooks() {
  const grid  = document.getElementById("booksGrid");
  const books = await dbAll("books");

  if (books.length === 0) {
    grid.innerHTML = `<p id="noBooksMsg">No books uploaded yet.</p>`;
    return;
  }

  grid.innerHTML = books.map(book => `
    <div class="book-card" data-book-id="${book.id}">
      <img src="${book.cover || 'https://via.placeholder.com/200x140?text=Book'}" alt="${book.name}" />
      <h4>${book.name}</h4>
      <p>${book.description}</p>
      <div class="card-actions">
        <button class="btn btn-accent"  onclick="enqueue('${book.id}', 'quiz')">Quiz</button>
        <button class="btn btn-outline" onclick="enqueue('${book.id}', 'summary')">Summary</button>
        <button class="btn btn-danger"  onclick="deleteBook('${book.id}')">Delete</button>
      </div>
    </div>
  `).join("");
}


// ══════════════════════════════════════════
//  DELETE BOOK
// ══════════════════════════════════════════

/**
 * Delete a book and all its associated data
 * @param {string} bookId - Book identifier
 */
async function deleteBook(bookId) {
  if (!confirm("Delete this book and all its data?")) return;
  await dbDel("books",      bookId);
  await dbDel("summaries",  bookId);
  await dbDel("quizzes",    bookId);
  await dbDel("taskCounts", bookId);
  renderBooks();
}


// ══════════════════════════════════════════
//  ALL QUIZZES PAGE
// ══════════════════════════════════════════

/**
 * Render all quizzes on the quizzes page
 */
async function renderAllQuizzes() {
  const container = document.getElementById("allQuizzes");
  const quizzes   = await dbAll("quizzes");

  if (quizzes.length === 0) {
    container.innerHTML = `<p class="muted">No quizzes yet.</p>`;
    return;
  }

  container.innerHTML = quizzes.map(q => `
    <div style="margin-bottom:2rem">
      <h3 style="margin-bottom:1rem; border-left:4px solid var(--accent); padding-left:0.6rem">${q.bookName}</h3>
      <h4 style="margin-bottom:0.5rem; color:var(--muted)">Questions</h4>
      ${renderQACards(q.questions)}
      <h4 style="margin:1rem 0 0.5rem; color:var(--muted)">Answers</h4>
      ${renderQACards(q.answers)}
    </div>
  `).join("");
}


// ══════════════════════════════════════════
//  ALL SUMMARIES PAGE
// ══════════════════════════════════════════

/**
 * Render all summaries on the summaries page
 */
async function renderAllSummaries() {
  const container = document.getElementById("allSummaries");
  const summaries = await dbAll("summaries");

  if (summaries.length === 0) {
    container.innerHTML = `<p class="muted">No summaries yet.</p>`;
    return;
  }

  container.innerHTML = summaries.map(s => `
    <div class="output-box" style="margin-bottom:1.5rem">
      <h3 style="margin-bottom:0.5rem">${s.bookName}</h3>
      <p style="white-space:pre-wrap">${s.summary}</p>
    </div>
  `).join("");
}


// ══════════════════════════════════════════
//  INIT
// ══════════════════════════════════════════

/**
 * Initialize the application
 */
(async () => {
  loadTheme();           // Load saved theme preference
  await openDB();        // Initialize database
  renderBooks();         // Render initial book list
})();
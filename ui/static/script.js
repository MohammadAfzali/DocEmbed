document.getElementById('searchForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const queryText = document.getElementById('queryText').value;
    const topN = document.getElementById('topN').value;
    const loading = document.getElementById('loading');
    const error = document.getElementById('error');
    const results = document.getElementById('results');

    // Reset UI
    loading.classList.remove('d-none');
    error.classList.add('d-none');
    results.innerHTML = '';

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query_text: queryText, top_n: parseInt(topN) })
        });

        const data = await response.json();

        loading.classList.add('d-none');

        if (!response.ok) {
            error.textContent = data.error || 'An error occurred';
            error.classList.remove('d-none');
            return;
        }

        if (data.results.length === 0) {
            results.innerHTML = '<p class="text-muted">No results found.</p>';
            return;
        }

        data.results.forEach(result => {
            const resultCard = document.createElement('div');
            resultCard.className = 'card result-card';
            resultCard.innerHTML = `
                <div class="card-header">
                    Document: ${result.doc_id}
                </div>
                <div class="card-body">
                    <p class="card-text">${result.text}</p>
                    <p class="text-muted">Score: ${result.score.toFixed(4)}</p>
                    <p class="text-muted">Chunk: ${result.chunk_id}</p>
                </div>
            `;
            results.appendChild(resultCard);
        });
    } catch (err) {
        loading.classList.add('d-none');
        error.textContent = 'Failed to connect to the server';
        error.classList.remove('d-none');
    }
});
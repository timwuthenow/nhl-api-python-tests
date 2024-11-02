document.addEventListener('DOMContentLoaded', function() {
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('date-picker').value = today;
    fetchRankings();
});

function fetchRankings() {
    const date = document.getElementById('date-picker').value;
    fetch(`/get_rankings?date=${date}`)
        .then(response => response.json())
        .then(data => {
            populateRankings(data);
        })
        .catch(error => console.error('Error:', error));
}

function populateRankings(rankings) {
    const tbody = document.getElementById('rankings-body');
    tbody.innerHTML = '';
    rankings.forEach((team) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${team.Rank}</td>
            <td>${team.Team}</td>
            <td><img src="/static/logos/${team.Team}.svg" alt="${team.Team} logo" class="team-logo"></td>
            <td class="score">${team.Score.toFixed(2)}</td>
            <td>${team['Recent PP%'].toFixed(2)}</td>
            <td>${team['Recent PK%'].toFixed(2)}</td>
            <td>${team['Season PP%'].toFixed(2)}</td>
            <td>${team['Season PK%'].toFixed(2)}</td>
            <td>
                <input type="range" min="-5" max="5" value="0" step="0.1" 
                       oninput="updateScore('${team.Team}', this.value)">
                <span class="adjustment">0%</span>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function updateScore(team, adjustment) {
    const row = event.target.closest('tr');
    const scoreCell = row.querySelector('.score');
    const adjustmentSpan = row.querySelector('.adjustment');
    
    const originalScore = parseFloat(scoreCell.textContent);
    const adjustedScore = originalScore * (1 + parseFloat(adjustment) / 100);
    
    scoreCell.textContent = adjustedScore.toFixed(2);
    adjustmentSpan.textContent = `${adjustment}%`;

    fetch('/update_score', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({team: team, adjustment: adjustment}),
    })
    .then(response => response.json())
    .then(data => console.log('Success:', data))
    .catch((error) => console.error('Error:', error));
}

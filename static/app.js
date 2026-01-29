async function fetchAlerts(){
  const res = await fetch('/alerts');
  const alerts = await res.json();
  const container = document.getElementById('alerts');
  container.innerHTML = '';
  if(alerts.length===0){
    container.innerHTML = '<p class="small">No current alerts (streaming sample data)...</p>';
    return;
  }
  alerts.forEach(a=>{
    const el = document.createElement('div');
    el.className = 'alert-card';
    el.innerHTML = `<strong>${a.analysis.category.toUpperCase()} (Severity ${a.analysis.severity})</strong>
      <p>${a.text}</p>
      <p class="small">${a.analysis.summary}</p>
      <p class="small">Indicators: ${ (a.analysis.indicators||[]).join(', ')}</p>`;
    container.appendChild(el);
  });
}

document.getElementById('analyzeBtn').addEventListener('click', async ()=>{
  const text = document.getElementById('tweetText').value;
  const res = await fetch('/analyze', {method:'POST',headers:{'Content-Type':'application/json'}, body: JSON.stringify({text})});
  const data = await res.json();
  document.getElementById('result').innerText = JSON.stringify(data, null, 2);
});

setInterval(fetchAlerts, 2000);
fetchAlerts();

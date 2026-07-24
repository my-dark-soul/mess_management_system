function updateTotals() {
  document.querySelectorAll("tbody tr").forEach(row => {
    const meal = parseFloat(row.querySelector(".meal-input").value) || 0;
    const gas = parseFloat(row.querySelector(".gas-input").value) || 0;
    row.querySelector(".total-cell").textContent = (meal + gas).toFixed(2);
  });
}

document.querySelectorAll(".meal-input, .gas-input").forEach(input => {
  input.addEventListener("input", updateTotals);
});

// Initial calculation
updateTotals();

// Save data
document.getElementById("saveFinancialButton").addEventListener("click", () => {
  const data = [];
  document.querySelectorAll("tbody tr").forEach(row => {
    const member_id = row.querySelector(".meal-input").dataset.memberId;
    const meal = parseFloat(row.querySelector(".meal-input").value) || 0;
    const gas = parseFloat(row.querySelector(".gas-input").value) || 0;
    data.push({ member_id, meal, gas });
  });

  fetch("/save_financial_data/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  })
  .then(res => res.json())
  .then(resp => alert(resp.message))
  .catch(err => console.error(err));
});
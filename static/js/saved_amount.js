document.getElementById("saveFinancialButton").addEventListener("click", function () {
    let rows = document.querySelectorAll("#financialTable tbody tr");
    let financialData = [];

    rows.forEach(row => {
        const memberId = row.dataset.memberId;
        const mealAmount = parseFloat(row.querySelector(".meal-input").value) || 0;
        const gasAmount = parseFloat(row.querySelector(".gas-input").value) || 0;

        financialData.push({
            member_id: parseInt(memberId),
            meal_amount: mealAmount,
            gas_amount: gasAmount
        });
    });

    console.log("Sending data:", financialData); // 🔹 Check in browser console

    fetch("/save_financial_data/", {  // Make sure this matches Flask route
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify(financialData)
    })
    .then(res => res.json())
    .then(resp => {
        alert(resp.message || "Data saved successfully!");
    })
    .catch(err => {
        console.error("Error:", err);
        alert("Failed to save data.");
    });
});

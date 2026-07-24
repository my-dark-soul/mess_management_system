function downloadPDF() {
    const { jsPDF } = window.jspdf;
    const doc = new jsPDF();

    // Title
    doc.setFontSize(16);
    doc.text("Meal Summary", 14, 15);

    // Get the table element
    const table = document.getElementById("table");

    // AutoTable from your HTML table
    doc.autoTable({
        html: table, // DOM element
        startY: 25,
        theme: 'grid',
        styles: {
            fontSize: 10,
            halign: 'center'
        },
        headStyles: {
            fillColor: [0, 112, 192], // 👈 Blue color for header
            textColor: 255,           // 👈 White text
            fontStyle: 'bold'
        }
    });

    // Save PDF
    doc.save('meal-summary.pdf');
}
// Research Rooms - Main JavaScript
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Auto-dismiss flash messages after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Simulate process updates in the OS simulation panel
    simulateProcessUpdates();
});

// Function to simulate process updates in the OS simulation panel
function simulateProcessUpdates() {
    const processList = document.querySelector('.process-list');
    if (!processList) return;

    // Update process status randomly every few seconds to simulate activity
    setInterval(function() {
        const processes = processList.querySelectorAll('.process-item');
        if (processes.length === 0) return;
        
        // Select a random process to update
        const randomProcess = processes[Math.floor(Math.random() * processes.length)];
        
        // Toggle between running and waiting
        if (randomProcess.classList.contains('running')) {
            randomProcess.classList.remove('running');
            randomProcess.classList.add('waiting');
            randomProcess.querySelector('.process-status').textContent = 'Queued';
        } else {
            randomProcess.classList.remove('waiting');
            randomProcess.classList.add('running');
            randomProcess.querySelector('.process-status').textContent = 'Running';
        }
        
        // Update progress bar
        const progressBar = document.querySelector('.progress-bar');
        if (progressBar) {
            const newWidth = Math.floor(Math.random() * 100) + '%';
            progressBar.style.width = newWidth;
        }
    }, 5000);
}
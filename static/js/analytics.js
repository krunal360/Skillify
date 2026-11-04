const teal  = '#4ECDC4';
const pink  = '#EC4899';
const amber = '#F59E0B';
const red   = '#EF4444';
const purple = '#8B5CF6';
const green = '#10B981';
const blue  = '#3B82F6';

const gridColor  = 'rgba(0,0,0,0.05)';
const labelColor = '#6c757d';

const baseOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
        legend: { display: false },
    },
    scales: {
        x: {
            grid: { color: gridColor },
            ticks: { color: labelColor, font: { size: 11 } },
        },
        y: {
            grid: { color: gridColor },
            ticks: { color: labelColor, font: { size: 11 } },
            beginAtZero: true,
        },
    },
};

// 1. User Growth
new Chart(document.getElementById('userGrowthChart'), {
    type: 'bar',
    data: {
        labels: userGrowthLabels,
        datasets: [{
            data: userGrowthData,
            backgroundColor: teal,
            borderRadius: 6,
        }]
    },
    options: baseOptions,
});

// 2. Booking Trend
new Chart(document.getElementById('bookingTrendChart'), {
    type: 'line',
    data: {
        labels: bookingTrendLabels,
        datasets: [{
            data: bookingTrendData,
            borderColor: pink,
            backgroundColor: 'rgba(236,72,153,0.08)',
            borderWidth: 2.5,
            pointBackgroundColor: pink,
            pointRadius: 4,
            tension: 0.4,
            fill: true,
        }]
    },
    options: baseOptions,
});

// 3. Skill Popularity (horizontal bar)
new Chart(document.getElementById('skillPopChart'), {
    type: 'bar',
    data: {
        labels: skillPopLabels,
        datasets: [{
            data: skillPopData,
            backgroundColor: teal,
            borderRadius: 4,
        }]
    },
    options: {
        ...baseOptions,
        indexAxis: 'y',
        scales: {
            x: { grid: { color: gridColor }, ticks: { color: labelColor, font: { size: 11 } }, beginAtZero: true },
            y: { grid: { display: false }, ticks: { color: labelColor, font: { size: 11 } } },
        },
    },
});

// 5. Trust Score Distribution
new Chart(document.getElementById('trustDistChart'), {
    type: 'bar',
    data: {
        labels: trustLabels,
        datasets: [{
            data: trustData,
            backgroundColor: [
                '#adb5bd', '#4ECDC4', '#3B82F6',
                '#F59E0B', '#10B981', '#8B5CF6'
            ],
            borderRadius: 6,
        }]
    },
    options: {
        ...baseOptions,
        plugins: { legend: { display: false } },
    },
});

// 6. Session Completion Donut
new Chart(document.getElementById('sessionDonutChart'), {
    type: 'doughnut',
    data: {
        labels: ['Completed', 'Cancelled', 'Upcoming'],
        datasets: [{
            data: [completedSessions, cancelledSessions, upcomingSessions],
            backgroundColor: [teal, red, amber],
            borderWidth: 0,
            hoverOffset: 6,
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '65%',
        plugins: {
            legend: { display: false },
        },
    },
});

// 7. Credit Flow
new Chart(document.getElementById('creditFlowChart'), {
    type: 'line',
    data: {
        labels: creditLabels,
        datasets: [
            {
                label: 'Credits Earned',
                data: creditsEarned,
                borderColor: teal,
                backgroundColor: 'rgba(78,205,196,0.08)',
                borderWidth: 2.5,
                pointBackgroundColor: teal,
                pointRadius: 4,
                tension: 0.4,
                fill: true,
            },
            {
                label: 'Credits Spent',
                data: creditsSpent,
                borderColor: pink,
                backgroundColor: 'rgba(236,72,153,0.06)',
                borderWidth: 2.5,
                pointBackgroundColor: pink,
                pointRadius: 4,
                tension: 0.4,
                fill: true,
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: true,
                position: 'top',
                labels: {
                    color: labelColor,
                    font: { size: 12 },
                    boxWidth: 12,
                    padding: 16,
                }
            },
        },
        scales: {
            x: { grid: { color: gridColor }, ticks: { color: labelColor, font: { size: 11 } } },
            y: { grid: { color: gridColor }, ticks: { color: labelColor, font: { size: 11 } }, beginAtZero: true },
        },
    },
});

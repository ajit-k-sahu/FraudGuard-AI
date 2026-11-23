/**
 * FraudGuard AI - Chart.js Telemetry Initializer
 * WCAG AA High-Contrast Dark Palette: Crisp Light Ticks, Clear Legends & Vibrant Series
 */

function initDashboardCharts(chartData) {
  if (!chartData || typeof Chart === 'undefined') return;

  const fontOptions = {
    family: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    size: 12,
    weight: '500'
  };

  const tooltipPluginConfig = {
    backgroundColor: '#0b1329',
    borderColor: '#233c70',
    borderWidth: 1,
    titleColor: '#ffffff',
    bodyColor: '#cbd5e1',
    padding: 10,
    cornerRadius: 8,
    displayColors: true
  };

  // 1. Transaction Outcome Donut Chart (Legit vs Fraud)
  const outcomeCanvas = document.getElementById('outcomeChart');
  if (outcomeCanvas && chartData.outcome_distribution) {
    new Chart(outcomeCanvas, {
      type: 'doughnut',
      data: {
        labels: chartData.outcome_distribution.labels,
        datasets: [{
          data: chartData.outcome_distribution.values,
          backgroundColor: ['#10b981', '#ef4444'],
          borderColor: '#152445',
          borderWidth: 3,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: '#cbd5e1', font: fontOptions, padding: 14 }
          },
          tooltip: tooltipPluginConfig
        },
        cutout: '72%'
      }
    });
  }

  // 2. Risk Distribution Doughnut Chart (Low, Medium, High)
  const riskCanvas = document.getElementById('riskChart');
  if (riskCanvas && chartData.risk_distribution) {
    new Chart(riskCanvas, {
      type: 'doughnut',
      data: {
        labels: chartData.risk_distribution.labels,
        datasets: [{
          data: chartData.risk_distribution.values,
          backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
          borderColor: '#152445',
          borderWidth: 3,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: '#cbd5e1', font: fontOptions, padding: 14 }
          },
          tooltip: tooltipPluginConfig
        },
        cutout: '72%'
      }
    });
  }

  // 3. Transaction Types Bar Chart
  const typeCanvas = document.getElementById('typeChart');
  if (typeCanvas && chartData.type_distribution) {
    new Chart(typeCanvas, {
      type: 'bar',
      data: {
        labels: chartData.type_distribution.labels,
        datasets: [{
          label: 'Transaction Count',
          data: chartData.type_distribution.values,
          backgroundColor: '#38bdf8',
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: tooltipPluginConfig
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: '#cbd5e1', font: fontOptions }
          },
          y: {
            grid: { color: 'rgba(255, 255, 255, 0.08)' },
            ticks: { color: '#cbd5e1', font: fontOptions, precision: 0 }
          }
        }
      }
    });
  }

  // 4. Temporal Trends Line Chart (Past 7 Days)
  const trendCanvas = document.getElementById('trendChart');
  if (trendCanvas && chartData.trend_data) {
    new Chart(trendCanvas, {
      type: 'line',
      data: {
        labels: chartData.trend_data.labels,
        datasets: [
          {
            label: 'Total Volume ($)',
            data: chartData.trend_data.volumes,
            borderColor: '#38bdf8',
            backgroundColor: 'rgba(56, 189, 248, 0.12)',
            fill: true,
            tension: 0.35,
            yAxisID: 'yVolume'
          },
          {
            label: 'Fraud Count',
            data: chartData.trend_data.fraud_txns,
            borderColor: '#f87171',
            backgroundColor: 'rgba(248, 113, 113, 0.25)',
            fill: false,
            tension: 0.2,
            borderDash: [4, 4],
            yAxisID: 'yCount'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: '#cbd5e1', font: fontOptions }
          },
          tooltip: tooltipPluginConfig
        },
        scales: {
          x: {
            grid: { color: 'rgba(255, 255, 255, 0.08)' },
            ticks: { color: '#cbd5e1', font: fontOptions }
          },
          yVolume: {
            type: 'linear',
            position: 'left',
            grid: { color: 'rgba(255, 255, 255, 0.08)' },
            ticks: {
              color: '#38bdf8',
              font: fontOptions,
              callback: value => '$' + Number(value).toLocaleString()
            }
          },
          yCount: {
            type: 'linear',
            position: 'right',
            grid: { display: false },
            ticks: { color: '#f87171', font: fontOptions, precision: 0 }
          }
        }
      }
    });
  }
}

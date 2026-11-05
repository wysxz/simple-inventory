window.chartColors = {
    red: "rgb(255, 99, 132)",
    pink: "rgb(255, 105, 180)",
    orange: "rgb(255, 159, 64)",
    yellow: "rgb(255, 205, 86)",
    green: "rgb(75, 192, 192)",
    blue: "rgb(54, 162, 235)",
    purple: "rgb(153, 102, 255)",
    grey: "rgb(201, 203, 207)"
};

// var summaryChartDataCount = summaryChartData.chart_count.map(function(rec) {
//     return dateify(rec);
// });
// console.log(summaryChartDataCount);
// var summaryChartDataProfit = summaryChartData.chart_gross.map(function(rec) {
//     return dateify(rec);
// });
// console.log(summaryChartDataProfit);

var color = Chart.helpers.color;
var summaryCountChart = new Chart(
    document.getElementById("summaryCountChart"), {
        type: "line",
        data: {
            labels: summaryChartData.chart_count.map(function(rec) {
                return rec.x.slice(11, 16);
            }),
            datasets: [{
                label: "交易笔数（每小时）",
                type: "line",
                backgroundColor: color(window.chartColors.green)
                    .alpha(0.5)
                    .rgbString(),
                borderColor: window.chartColors.green,
                data: summaryChartData.chart_count.map(function(rec) {
                    return rec.y;
                })
            }]
        },
        options: {
            title: {
                text: "今日交易笔数"
            },
            scales: {
                xAxes: [{
                    type: "category",
                    ticks: {
                        autoSkip: false,
                        minRotation: 90,
                        maxRotation: 90,
                        fontSize: 10
                    }
                }],
                yAxes: [{
                    ticks: {
                        beginAtZero: true,
                        stepSize: 1,
                        precision: 0
                    }
                }]
            },
            elements: {
                line: {
                    tension: 0 // disables bezier curves
                }
            }
        }
    }
);

var summarySalesChart = new Chart(
    document.getElementById("summarySalesChart"), {
        type: "line",
        data: {
            labels: summaryChartData.chart_gross.map(function(rec) {
                return rec.x.slice(11, 16);
            }),
            datasets: [{
                    label: "全部销售单总额（人民币）",
                    type: "line",
                    backgroundColor: color(window.chartColors.blue)
                        .alpha(0.5)
                        .rgbString(),
                    borderColor: window.chartColors.blue,
                    borderWidth: 2,
                    fill: false,
                    showLine: true,
                    pointRadius: 3,
                    data: summaryChartData.chart_gross.map(function(rec) {
                        return rec.y;
                    })
                },
                {
                    label: "毛利润（人民币）",
                    type: "line",
                    backgroundColor: color(window.chartColors.pink)
                        .alpha(0.5)
                        .rgbString(),
                    borderColor: window.chartColors.pink,
                    borderWidth: 2,
                    fill: false,
                    showLine: true,
                    pointRadius: 3,
                    data: summaryChartData.chart_profit.map(function(rec) {
                        return rec.y;
                    })
                }
            ]
        },
        options: {
            title: {
                text: "今日销售额"
            },
            scales: {
                xAxes: [{
                    type: "category",
                    ticks: {
                        autoSkip: false,
                        minRotation: 90,
                        maxRotation: 90,
                        fontSize: 10
                    }
                }],
                yAxes: [{
                    ticks: {
                        callback: function(value) {
                            return "¥" + Number(value).toLocaleString("zh-CN");
                        }
                    }
                }]
            },
            tooltips: {
                callbacks: {
                    label: function(tooltipItem, data) {
                        var label = data.datasets[tooltipItem.datasetIndex].label || "";
                        var value = Number(tooltipItem.yLabel).toLocaleString("zh-CN", {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2
                        });
                        return label + ": ¥" + value;
                    }
                }
            },
            elements: {
                line: {
                    tension: 0 // disables bezier curves
                }
            }
        }
    }
);
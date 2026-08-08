(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var accent3 = style.getPropertyValue('--accent3').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var warning = style.getPropertyValue('--warning').trim();
  var danger = style.getPropertyValue('--danger').trim();

  // --- Chart 1: Cache vs DB ---
  var chart1 = echarts.init(document.getElementById('chart-cache-db'), null, { renderer: 'svg' });
  chart1.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true,
      backgroundColor: bg2,
      borderColor: rule,
      textStyle: { color: ink }
    },
    legend: {
      data: ['DB 延迟', 'Cache 延迟'],
      textStyle: { color: muted },
      top: 0
    },
    grid: { left: '8%', right: '8%', bottom: '10%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: ['Shop 1', 'Shop 2', 'Shop 3', 'Shop 4', 'Shop 5', 'Shop 6', 'Shop 7', 'Shop 8', 'Shop 9', 'Shop 10'],
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'value',
      name: '延迟 (ms)',
      nameTextStyle: { color: muted, fontSize: 11 },
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    series: [
      {
        name: 'DB 延迟',
        type: 'bar',
        data: [7.77, 0.71, 0.64, 0.54, 0.53, 0.50, 0.49, 0.48, 0.50, 0.47],
        itemStyle: { color: accent },
        barWidth: '30%'
      },
      {
        name: 'Cache 延迟',
        type: 'bar',
        data: [0.76, 0.60, 0.57, 0.54, 0.54, 0.47, 0.49, 0.50, 0.47, 0.47],
        itemStyle: { color: accent3 },
        barWidth: '30%'
      }
    ]
  });
  window.addEventListener('resize', function() { chart1.resize(); });

  // --- Chart 2: Concurrent Query Latency ---
  var chart2 = echarts.init(document.getElementById('chart-concurrent'), null, { renderer: 'svg' });
  chart2.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true,
      backgroundColor: bg2,
      borderColor: rule,
      textStyle: { color: ink },
      formatter: function(params) {
        return params[0].name + '<br/>' + params[0].seriesName + ': ' + params[0].value + ' ms';
      }
    },
    grid: { left: '8%', right: '8%', bottom: '10%', top: '12%', containLabel: true },
    xAxis: {
      type: 'category',
      data: ['P50 (中位数)', 'P90', 'P95', 'P99', 'Max'],
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'value',
      name: '延迟 (ms)',
      nameTextStyle: { color: muted, fontSize: 11 },
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    series: [{
      name: '延迟',
      type: 'bar',
      data: [
        { value: 8.18, itemStyle: { color: accent3 } },
        { value: 14.91, itemStyle: { color: accent2 } },
        { value: 17.58, itemStyle: { color: warning } },
        { value: 21.74, itemStyle: { color: danger } },
        { value: 26.10, itemStyle: { color: danger } }
      ],
      barWidth: '50%',
      label: {
        show: true,
        position: 'top',
        color: ink,
        fontSize: 11,
        formatter: '{c} ms'
      }
    }]
  });
  window.addEventListener('resize', function() { chart2.resize(); });

  // --- Chart 3: Seckill Latency & Stock ---
  var chart3 = echarts.init(document.getElementById('chart-seckill'), null, { renderer: 'svg' });
  chart3.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true,
      backgroundColor: bg2,
      borderColor: rule,
      textStyle: { color: ink }
    },
    legend: {
      data: ['延迟 (ms)', '库存'],
      textStyle: { color: muted },
      top: 0
    },
    grid: { left: '8%', right: '8%', bottom: '10%', top: '15%', containLabel: true },
    xAxis: {
      type: 'category',
      data: ['P50', 'P90', 'P95', 'P99', 'Max'],
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } }
    },
    yAxis: [
      {
        type: 'value',
        name: '延迟 (ms)',
        nameTextStyle: { color: muted, fontSize: 11 },
        axisLabel: { color: muted, fontSize: 11 },
        axisLine: { lineStyle: { color: rule } },
        splitLine: { lineStyle: { color: rule, type: 'dashed' } }
      },
      {
        type: 'value',
        name: '库存',
        nameTextStyle: { color: muted, fontSize: 11 },
        axisLabel: { color: muted, fontSize: 11 },
        axisLine: { lineStyle: { color: rule } },
        splitLine: { show: false }
      }
    ],
    series: [
      {
        name: '延迟 (ms)',
        type: 'bar',
        data: [22.01, 31.12, 31.62, 31.67, 31.67],
        itemStyle: { color: accent },
        barWidth: '40%',
        label: {
          show: true,
          position: 'top',
          color: ink,
          fontSize: 10,
          formatter: '{c} ms'
        }
      },
      {
        name: '库存',
        type: 'line',
        yAxisIndex: 1,
        data: [100, 90, 80, 70, 70],
        itemStyle: { color: accent3 },
        lineStyle: { width: 2 },
        symbol: 'circle',
        symbolSize: 6,
        label: {
          show: true,
          color: accent3,
          fontSize: 10
        }
      }
    ]
  });
  window.addEventListener('resize', function() { chart3.resize(); });

  // --- Chart 4: Rate Limit Pie ---
  var chart4 = echarts.init(document.getElementById('chart-rate-limit'), null, { renderer: 'svg' });
  chart4.setOption({
    animation: false,
    tooltip: {
      trigger: 'item',
      appendToBody: true,
      backgroundColor: bg2,
      borderColor: rule,
      textStyle: { color: ink },
      formatter: '{b}: {c} ({d}%)'
    },
    legend: {
      bottom: 10,
      textStyle: { color: muted },
      data: ['放行', '限流拦截']
    },
    series: [{
      type: 'pie',
      radius: ['40%', '65%'],
      center: ['50%', '45%'],
      avoidLabelOverlap: false,
      label: {
        show: true,
        color: ink,
        fontSize: 12,
        formatter: '{b}\n{d}%'
      },
      labelLine: {
        lineStyle: { color: rule }
      },
      data: [
        { value: 2, name: '放行', itemStyle: { color: accent3 } },
        { value: 18, name: '限流拦截', itemStyle: { color: danger } }
      ]
    }]
  });
  window.addEventListener('resize', function() { chart4.resize(); });
})();

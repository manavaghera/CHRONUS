
> Data: 55,371 tweets from June 2010 to May 2026 Place `elon_musk_cleaned.csv` inside a `data/` folder in your vault.

---

## Top 20 Tweets by Likes

```dataviewjs
const csv = await dv.io.csv("01-Raw-Data/Tweets/elon_musk_cleaned.csv")
const rows = csv.values
  .filter(r => String(r.is_elon_original) === "True")
  .sort((a, b) => Number(b.likes) - Number(a.likes))
  .slice(0, 20)
dv.table(
  ["Date", "Tweet", "Likes", "RTs", "Engagement"],
  rows.map(r => [
    String(r.date_str),
    String(r.text).substring(0, 80) + "...",
    Number(r.likes).toLocaleString(),
    Number(r.retweets).toLocaleString(),
    Number(r.engagement).toLocaleString()
  ])
)
```

---

## Tweets Per Year

```dataviewjs
const csv = await dv.io.csv("01-Raw-Data/Tweets/elon_musk_cleaned.csv")
const years = {}
csv.values
  .filter(r => String(r.is_elon_original) === "True" && r.year)
  .forEach(r => {
    const y = String(r.year).split(".")[0]
    years[y] = (years[y] || 0) + 1
  })
const sorted = Object.entries(years).sort((a, b) => Number(a[0]) - Number(b[0]))
const chartData = {
  type: "bar",
  data: {
    labels: sorted.map(e => e[0]),
    datasets: [{
      label: "Tweets",
      data: sorted.map(e => e[1]),
      backgroundColor: "rgba(29,155,240,0.7)",
      borderColor: "rgba(29,155,240,1)",
      borderWidth: 1
    }]
  },
  options: {
    plugins: { title: { display: true, text: "Tweets Per Year" } }
  }
}
window.renderChart(chartData, this.container)
```

---

## Average Engagement by Day of Week

```dataviewjs
const csv = await dv.io.csv("01-Raw-Data/Tweets/elon_musk_cleaned.csv")
const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
const totals = {}
const counts = {}
csv.values
  .filter(r => String(r.is_elon_original) === "True")
  .forEach(r => {
    const d = String(r.day_of_week)
    totals[d] = (totals[d] || 0) + Number(r.engagement || 0)
    counts[d] = (counts[d] || 0) + 1
  })
const chartData = {
  type: "bar",
  data: {
    labels: days,
    datasets: [{
      label: "Avg Engagement",
      data: days.map(d => Math.round((totals[d] || 0) / (counts[d] || 1))),
      backgroundColor: "rgba(249,24,128,0.7)",
      borderColor: "rgba(249,24,128,1)",
      borderWidth: 1
    }]
  },
  options: {
    plugins: { title: { display: true, text: "Avg Engagement by Day" } }
  }
}
window.renderChart(chartData, this.container)
```

---

## Monthly Tweet Volume (Line Chart)

```dataviewjs
const csv = await dv.io.csv("01-Raw-Data/Tweets/elon_musk_cleaned.csv")
const months = {}
csv.values
  .filter(r => String(r.is_elon_original) === "True" && r.date_str)
  .forEach(r => {
    const m = String(r.date_str).substring(0, 7)
    months[m] = (months[m] || 0) + 1
  })
const sorted = Object.entries(months).sort((a, b) => a[0].localeCompare(b[0]))
const chartData = {
  type: "line",
  data: {
    labels: sorted.map(e => e[0]),
    datasets: [{
      label: "Tweets per Month",
      data: sorted.map(e => e[1]),
      borderColor: "rgba(29,155,240,1)",
      backgroundColor: "rgba(29,155,240,0.1)",
      fill: true,
      tension: 0.3,
      pointRadius: 0
    }]
  },
  options: {
    plugins: { title: { display: true, text: "Monthly Tweet Volume" } },
    scales: { x: { ticks: { maxTicksLimit: 20 } } }
  }
}
window.renderChart(chartData, this.container)
```

---

## Tweet Type Breakdown (Pie)

```dataviewjs
const csv = await dv.io.csv("01-Raw-Data/Tweets/elon_musk_cleaned.csv")
let originals = 0
let replies = 0
let rts = 0
let quotes = 0
csv.values.forEach(r => {
  if (String(r.is_rt) === "True") { rts++ }
  else if (String(r.is_reply) === "True") { replies++ }
  else if (String(r.is_quote) === "True") { quotes++ }
  else { originals++ }
})
const chartData = {
  type: "doughnut",
  data: {
    labels: ["Original", "Reply", "Retweet", "Quote"],
    datasets: [{
      data: [originals, replies, rts, quotes],
      backgroundColor: [
        "rgba(29,155,240,0.8)",
        "rgba(0,186,124,0.8)",
        "rgba(249,24,128,0.8)",
        "rgba(255,173,31,0.8)"
      ]
    }]
  },
  options: {
    plugins: { title: { display: true, text: "Tweet Type Breakdown" } }
  }
}
window.renderChart(chartData, this.container)
```

---

## Top 10 Most Replied Tweets

```dataviewjs
const csv = await dv.io.csv("01-Raw-Data/Tweets/elon_musk_cleaned.csv")
const rows = csv.values
  .filter(r => String(r.is_elon_original) === "True")
  .sort((a, b) => Number(b.replies) - Number(a.replies))
  .slice(0, 10)
dv.table(
  ["Date", "Tweet", "Replies", "Likes"],
  rows.map(r => [
    String(r.date_str),
    String(r.text).substring(0, 80) + "...",
    Number(r.replies).toLocaleString(),
    Number(r.likes).toLocaleString()
  ])
)
```

---

## Quick Stats

```dataviewjs
const csv = await dv.io.csv("01-Raw-Data/Tweets/elon_musk_cleaned.csv")
const all = csv.values.filter(r => String(r.is_elon_original) === "True")
const totalLikes = all.reduce((s, r) => s + Number(r.likes || 0), 0)
const totalRTs = all.reduce((s, r) => s + Number(r.retweets || 0), 0)
const avgEng = Math.round(all.reduce((s, r) => s + Number(r.engagement || 0), 0) / all.length)

dv.paragraph("**Total Original Tweets:** " + all.length.toLocaleString())
dv.paragraph("**Total Likes:** " + totalLikes.toLocaleString())
dv.paragraph("**Total Retweets:** " + totalRTs.toLocaleString())
dv.paragraph("**Avg Engagement per Tweet:** " + avgEng.toLocaleString())
```
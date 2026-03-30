# Sample Runs 🌍

Here’s a look at what happens behind the scenes when you actually prompt the application. I wanted to show both what the user types, and what the agents are passing around internally.

### Prompting a Trip to Nepal

**What I typed into the UI:**

> _"I want a relaxed 3-day trip to Pokhara with nature and cafés."_

First, the **Planner Node** grabbed that text and formatted it into a structured state variable so the rest of the agents knew exactly what the boundaries were:

```json
{
  "destination": "Pokhara",
  "days": 3,
  "budget": "medium",
  "pace": "relaxed",
  "interests": ["nature", "cafes"]
}
```

Then the Researcher gathered facts, the Builder drafted it, and the Constraint Checker evaluated it to make sure it fit the "relaxed" vibe and didn't blow the budget.

**Internal logs from the Constraint Checker:**

> **PASSED ✓** | Issues: 0 | Rebuild count: 1

Finally, the Reviewer node polished it up. Here is the exact output it generated on the UI:

---

**TRIP SUMMARY**
Get ready for a serene 3-day getaway to Pokhara! This itinerary blends the best of Nepal’s stunning nature with its cozy café culture, allowing you to unwind at a relaxed pace while soaking in breathtaking Himalayan views.

**BUDGET ESTIMATE**

- **Accommodation:** $150 total
- **Food:** $90 total
- **Transport:** $30 total
- **Activities:** $45 total
- **Misc:** $30 total
- **Total Estimate:** $345 - $350 (Within your medium budget)

**🗓 DAY-BY-DAY ITINERARY**

**Day 1: Arrival & Lakeside Leisure**

- **Activities:** Stroll along the beautiful Phewa Lake; enjoy a relaxing boat ride to the Tal Barahi Temple.
- **Breakfast:** Coffee and a light pastry at Himalayan Java Coffee.
- **Lunch:** Wood-fired pizza at Caffe Concerto.
- **Dinner:** Traditional Nepali thali at Moondance Restaurant.
- **Accommodation:** Mid-range hotel near Lakeside (e.g., Mount Kailash Resort).

**Day 2: Sunrise & Scenic Views**

- **Activities:** Early morning drive to Sarangkot for a spectacular sunrise over the Annapurna range; visit the Peace Pagoda (Shanti Stupa) in the afternoon.
- **Breakfast:** Breakfast with a view at Sarangkot.
- **Lunch:** Fresh salads and sandwiches at AM/PM Organic Cafe.
- **Dinner:** Lakeside dining at The Olive Cafe.
- **Accommodation:** Mid-range hotel near Lakeside.

**Day 3: Nature Walks & Departure**

- **Activities:** Morning visit to Devi's Fall and Gupteshwor Cave; final café-hopping for souvenirs.
- **Breakfast:** Hearty breakfast at French Creperie.
- **Lunch:** Light lunch at Krazy Gecko Bar & Rest.

**FOOD & DINING HIGHLIGHTS**

- **Himalayan Java Coffee:** Perfect for starting your day with locally sourced coffee.
- **Caffe Concerto:** Renowned for excellent Italian cuisine right by the lake.
- **Moondance Restaurant:** A must-visit for trying hearty Nepali and continental dishes.

**TIPS & NOTES**

- **Best Time to Visit:** September to November or March to May for clear mountain views.
- **Transport:** Taxis are readily available; negotiate fares beforehand. For short distances around Lakeside, walking is the best way to explore.

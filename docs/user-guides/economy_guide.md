---
title: Classroom Economy Guide
category: user-guides
description: Teacher-friendly ranges and examples for pricing, rent, insurance, balance checks, and policy modes.
roles: [teacher]
related:
  - user-guides/features/teacher/economy/economic-engine
  - user-guides/features/teacher/economy/policy-mode-rebalancer
---

# Classroom Economy Guide

This guide helps teachers set prices and fees that keep the classroom economy balanced and motivating. Use it alongside the Economic Engine and the economy policy/rebalance workflow.

## Quick start
1. Set payroll first so you have a baseline for weekly earnings.
2. Note your Classroom Wage Index (CWI).
3. Use the ranges below to set rent, utilities, store pricing, fines, and insurance.
4. Pick the policy mode that matches how tight or forgiving you want the class economy to feel.
5. Do a quick affordability check before you announce changes.

## Key concept: Classroom Wage Index (CWI)

CWI is the expected weekly pay for a student who attends all sessions.

```
CWI = expected week_total_pay for perfect attendance
```

## Economy policy modes

Policy mode changes the recommendation bands you use when reviewing pricing, bills, and savings pressure.

### Tight

- More budgeting pressure
- Higher fixed-cost expectations
- Lower savings target

### Default

- Balanced baseline
- Moderate pressure
- Standard savings target

### Comfortable

- More breathing room
- Lower fixed-cost pressure
- Higher savings target

## Recommended ranges (based on CWI)

Use these ranges as starting points and adjust for your class goals. The ratios below apply to your chosen billing or pricing cycle.

### Rent

| Policy | Range | Typical midpoint |
| --- | --- | --- |
| Tight | 0.70x to 0.80x CWI | 0.75x |
| Default | 0.60x to 0.75x CWI | 0.675x |
| Comfortable | 0.50x to 0.65x CWI | 0.575x |

If your rent is billed monthly or on another cycle, convert the weekly target into that cycle before comparing values.

### Utilities or fixed fees

| Policy | Range | Typical midpoint |
| --- | --- | --- |
| Tight | 0.07x to 0.12x CWI | 0.095x |
| Default | 0.05x to 0.10x CWI | 0.075x |
| Comfortable | 0.04x to 0.08x CWI | 0.06x |

### Store item pricing tiers

#### Tight

| Tier | Range |
| --- | --- |
| Basic | 0.01x to 0.03x CWI |
| Standard | 0.02x to 0.04x CWI |
| Premium | 0.04x to 0.12x CWI |
| Luxury | 0.12x to 0.24x CWI |

#### Default

| Tier | Range |
| --- | --- |
| Basic | 0.01x to 0.03x CWI |
| Standard | 0.02x to 0.05x CWI |
| Premium | 0.05x to 0.15x CWI |
| Luxury | 0.15x to 0.30x CWI |

#### Comfortable

| Tier | Range |
| --- | --- |
| Basic | 0.02x to 0.04x CWI |
| Standard | 0.03x to 0.06x CWI |
| Premium | 0.06x to 0.18x CWI |
| Luxury | 0.18x to 0.35x CWI |

### Insurance

#### Premiums

| Policy | Range | Typical midpoint |
| --- | --- | --- |
| Tight | 0.06x to 0.14x CWI | 0.09x |
| Default | 0.05x to 0.12x CWI | 0.08x |
| Comfortable | 0.04x to 0.10x CWI | 0.07x |

#### Coverage

| Policy | Range vs premium |
| --- | --- |
| Tight | 2.5x to 4.0x |
| Default | 3.0x to 5.0x |
| Comfortable | 4.0x to 6.0x |

#### Period payout cap

| Policy | Range vs premium |
| --- | --- |
| Tight | 5.0x to 8.0x |
| Default | 6.0x to 10.0x |
| Comfortable | 8.0x to 12.0x |

#### Waiting period guidance

| Policy | Recommended range |
| --- | --- |
| Tight | 10-14 days |
| Default | 7 days |
| Comfortable | 3-7 days |

If you set coverage above 5x premium or a cap outside 6x-10x, expect more volatility.

### Fines

| Policy | Range | Typical midpoint |
| --- | --- | --- |
| Tight | 0.07x to 0.18x CWI | 0.11x |
| Default | 0.05x to 0.15x CWI | 0.10x |
| Comfortable | 0.04x to 0.12x CWI | 0.08x |

Try to keep fine sizes consistent so students can predict consequences.

### Savings interest

Savings interest is a motivation tool. Keep it modest.

- APY: 6% to 18%
- Monthly rate: 0.5% to 1.5% (default about 1%)

## Affordability check

A student with perfect attendance should still save money after core costs.

```
weekly_savings = CWI - (rent / weeks_in_rent_cycle) - utilities - average_store_cost
```

Typical minimum savings targets:

- Tight: about 5% of CWI
- Default: about 10% of CWI
- Comfortable: about 15% of CWI

If students are consistently broke, lower rent or fines, reduce utilities, raise wages, or switch to a more forgiving policy mode.

## Rebalancing

Changing policy mode updates your target recommendation profile, but your current class settings do not automatically change at the same moment.

Use the rebalance review when you want the system to suggest updated values for supported settings.

See [Economic Policy and Rebalancing](features/teacher/economy/policy-mode-rebalancer.md) for the teacher workflow.

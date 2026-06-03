---
name: Multi-Agent Learning System
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#3c494e'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#6c797f'
  outline-variant: '#bbc9cf'
  surface-tint: '#00677f'
  primary: '#00677f'
  on-primary: '#ffffff'
  primary-container: '#00d1ff'
  on-primary-container: '#00566a'
  inverse-primary: '#4cd6ff'
  secondary: '#585e6c'
  on-secondary: '#ffffff'
  secondary-container: '#dde2f3'
  on-secondary-container: '#5e6473'
  tertiary: '#4d6265'
  on-tertiary: '#ffffff'
  tertiary-container: '#aec4c7'
  on-tertiary-container: '#3d5254'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b7eaff'
  primary-fixed-dim: '#4cd6ff'
  on-primary-fixed: '#001f28'
  on-primary-fixed-variant: '#004e60'
  secondary-fixed: '#dde2f3'
  secondary-fixed-dim: '#c1c6d7'
  on-secondary-fixed: '#161c27'
  on-secondary-fixed-variant: '#414754'
  tertiary-fixed: '#d0e7ea'
  tertiary-fixed-dim: '#b4cbce'
  on-tertiary-fixed: '#091f21'
  on-tertiary-fixed-variant: '#364a4d'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  h1:
    fontFamily: Source Han Sans CN
    fontSize: 40px
    fontWeight: '700'
    lineHeight: '1.2'
  h2:
    fontFamily: Source Han Sans CN
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.3'
  h3:
    fontFamily: Source Han Sans CN
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.4'
  body-lg:
    fontFamily: Source Han Sans CN
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Source Han Sans CN
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.6'
  label-sm:
    fontFamily: Source Han Sans CN
    fontSize: 13px
    fontWeight: '500'
    lineHeight: '1.0'
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  xs: 4px
  sm: 12px
  md: 24px
  lg: 48px
  xl: 80px
  gutter: 24px
  margin: 32px
---

## Brand & Style

The brand personality of this design system is **Analytical, Intelligent, and Lucid**. Designed specifically for a Multi-Agent Learning System focused on "Data Structures" (数据结构), it prioritizes cognitive ease and structural clarity. The visual language aims to evoke a sense of professional academic rigor while maintaining the cutting-edge feel of autonomous AI agents.

The chosen style is **Minimalism with a Technical Edge**. By utilizing a generous amount of negative space and a clinical light-mode palette, the design system ensures that complex data visualizations—such as linked lists, trees, and graphs—remain the focal point. The interface avoids unnecessary decoration, relying instead on precise alignment and subtle depth to guide the learner's mental model of abstract concepts.

## Colors

The color strategy for this design system centers on high-visibility functional accents.
- **Primary Cyan (#00D1FF):** Used for "Active" states, primary actions, and representing "Live" agents within the learning environment. It symbolizes intelligence and flow.
- **Surface Background (#FCF8F9):** A warm-tinted white that reduces eye strain during long study sessions compared to pure #FFFFFF.
- **Secondary Slate (#1A202C):** Provides high-contrast grounding for primary navigation and header text to ensure professional readability.
- **Success/Error:** Use standard semantic greens and reds, but desaturated to match the minimalist aesthetic.

## Typography

This design system utilizes **Source Han Sans CN (思源黑体)** for all Simplified Chinese text to provide a clean, modern, and highly legible experience across all screen densities. The typographic hierarchy is strictly enforced to help users distinguish between instructional content (正文), agent logs (日志), and structural labels (标签).

- **Headers:** Bold and authoritative to clearly define the hierarchy of data structure topics (e.g., "二叉树遍历").
- **Body Text:** Optimized for long-form reading with a comfortable 1.6 line-height.
- **Monospace (Optional):** For code snippets and data values, use a clean monospaced font to maintain alignment in array or matrix visualizations.

## Layout & Spacing

This design system adopts a **Fixed Grid System** for the primary content area (1280px max-width) to ensure that complex data structure diagrams do not become distorted on ultra-wide monitors. 

A 12-column grid is used with **24px gutters**, allowing for flexible sidebars that house "Agent Controls" (智能体控制区) while the main stage hosts the visualization. A strictly 8px-based spatial rhythm ensures that every element—from the smallest checkbox to the largest card—feels intentional and structured, mirroring the logic of the data structures being taught.

## Elevation & Depth

To maintain a minimalist aesthetic without appearing "flat" or "unclickable," this design system uses **Ambient Shadows** and **Tonal Layering**.

- **Level 0 (Background):** #FCF8F9.
- **Level 1 (Cards/Panels):** Pure white (#FFFFFF) with a very soft, diffused shadow (0px 4px 20px rgba(0, 0, 0, 0.04)). This is used for the main workspace and content blocks.
- **Level 2 (Floating/Active):** Slightly more pronounced shadow (0px 8px 30px rgba(0, 209, 255, 0.1)) used for active agents or modals.
- **Interaction:** Buttons use a subtle "press-in" effect rather than high-elevation shadows to maintain a sleek, modern profile.

## Shapes

In alignment with the "ROUND_FOUR" requirement, this design system utilizes a **Rounded (Level 2)** shape language. This translates to a base corner radius of **8px (0.5rem)** for standard components.

- **Small Components (Buttons, Inputs):** 8px radius for a approachable yet professional feel.
- **Large Components (Cards, Modals):** 16px (1rem) radius to soften the large blocks of information.
- **Data Nodes:** Circular or highly rounded containers to represent "Nodes" (节点) in trees and graphs, contrasting against the rectangular layout containers.

## Components

- **Buttons (按钮):** Primary buttons use the Cyan (#00D1FF) background with white text. Ghost buttons use a 1px border of the same cyan for secondary actions like "Reset Layout" (重置布局).
- **Cards (卡片):** White background, 16px rounded corners, and a subtle light gray border (#E2E8F0) to define boundaries without heavy shadows.
- **Input Fields (输入框):** Minimalist design with a 1px border that glows Cyan on focus. Labels are placed above the field in "label-sm" typography.
- **Chips/Status (状态标签):** Used to indicate Agent status. For example, "运行中" (Running) uses a light cyan background with dark cyan text.
- **Data Structure Visualizer (数据结构可视化器):** High-clarity lines (1.5px thickness) connecting nodes. Nodes should be clearly labeled in Simplified Chinese.
- **Agent Avatars (智能体头像):** Simple geometric icons or stylized initials within a circle, color-coded by the agent's specific role (e.g., Search Agent, Sort Agent).
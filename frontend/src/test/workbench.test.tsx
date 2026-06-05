import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from '../App'

describe('Lumen workbench', () => {
  it('renders the workbench-first home screen', () => {
    render(<App />)

    expect(screen.getByText('Lumen')).toBeInTheDocument()
    expect(screen.getByText('Ask or capture')).toBeInTheDocument()
    expect(screen.getByText('Memory Inbox')).toBeInTheDocument()
    expect(screen.getByText('Context Now')).toBeInTheDocument()
    expect(screen.getByText('Recent Sources')).toBeInTheDocument()
    expect(screen.getByText('Daily Review')).toBeInTheDocument()
  })
})

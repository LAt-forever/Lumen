import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { MemoryGraph } from './MemoryGraph'

const sampleGraph = {
  center_memory_id: 1,
  nodes: [
    { id: 1, text: 'Center', memory_type: 'preference', status: 'active' },
    { id: 2, text: 'Related', memory_type: 'fact', status: 'active' },
  ],
  edges: [
    {
      id: 10,
      source_memory_id: 1,
      target_memory_id: 2,
      relation_type: 'related_to' as const,
      provenance: 'user',
      strength: 70,
      status: 'active' as const,
    },
  ],
}

describe('MemoryGraph', () => {
  it('renders node labels', () => {
    render(<MemoryGraph graph={sampleGraph} width={400} height={300} onSelectNode={() => {}} />)
    expect(screen.getByText('Center')).toBeInTheDocument()
    expect(screen.getByText('Related')).toBeInTheDocument()
  })
})

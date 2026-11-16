import {describe,it,expect} from 'vitest'
import {renderToStaticMarkup} from 'react-dom/server'
import {Streamdown} from 'streamdown'

describe('complete answer Markdown',()=>{
  it('renders an intact GFM table with literal pipes, emphasis, headings and lists',()=>{
    const markdown='## Fees\n\n| Programme | Tuition / semester |\n| --- | ---: |\n| BSCS | **Rs. 185,000** |\n| Track A \\| B | Rs. 190,000 |\n\n### Steps\n\n1. Apply.\n2. Pay.\n\n- Keep the receipt.\n'
    const html=renderToStaticMarkup(<Streamdown mode="static" parseIncompleteMarkdown={false}>{markdown}</Streamdown>)
    expect(html).toContain('<table')
    expect(html).toContain('<thead')
    expect(html).toContain('Track A | B')
    expect(html).toContain('data-streamdown="strong"')
    expect(html).toContain('<ol')
    expect(html).toContain('<ul')
    expect(html).not.toContain('| ---')
  })
})

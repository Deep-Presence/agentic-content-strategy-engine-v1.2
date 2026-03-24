declare module 'react-plotly.js' {
  import { Component } from 'react';
  import Plotly from 'plotly.js';

  interface PlotParams {
    data: Plotly.Data[];
    layout?: Partial<Plotly.Layout>;
    config?: Partial<Plotly.Config>;
    frames?: Plotly.Frame[];
    revision?: number;
    onInitialized?: (figure: Readonly<{ data: Plotly.Data[]; layout: Partial<Plotly.Layout> }>, graphDiv: HTMLElement) => void;
    onUpdate?: (figure: Readonly<{ data: Plotly.Data[]; layout: Partial<Plotly.Layout> }>, graphDiv: HTMLElement) => void;
    onPurge?: (figure: Readonly<{ data: Plotly.Data[]; layout: Partial<Plotly.Layout> }>, graphDiv: HTMLElement) => void;
    onError?: (err: Error) => void;
    useResizeHandler?: boolean;
    style?: React.CSSProperties;
    className?: string;
    [key: string]: unknown;
  }

  class Plot extends Component<PlotParams> {}
  export default Plot;
}

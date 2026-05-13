/**
 * Компонент для обработки ошибок React
 */

import React from 'react';
import './ErrorBoundary.css';

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({
      error,
      errorInfo,
    });
  }

  handleReload = () => {
    window.location.reload();
  };

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-boundary-content">
            <div className="error-icon">Ошибка</div>
            <h2>Что-то пошло не так</h2>
            <p>Произошла ошибка при отображении компонента.</p>
            {this.state.error && (
              <p className="error-boundary-hint">
                {String(this.state.error.message || this.state.error).slice(0, 400)}
              </p>
            )}
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="error-details">
                <summary>Детали ошибки (только в режиме разработки)</summary>
                <pre className="error-message">{this.state.error.toString()}</pre>
                {this.state.errorInfo && (
                  <pre className="error-stack">{this.state.errorInfo.componentStack}</pre>
                )}
              </details>
            )}
            <div className="error-actions">
              <button onClick={this.handleReset} className="button button-primary">
                Попробовать снова
              </button>
              <button onClick={this.handleReload} className="button button-secondary">
                Перезагрузить страницу
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;


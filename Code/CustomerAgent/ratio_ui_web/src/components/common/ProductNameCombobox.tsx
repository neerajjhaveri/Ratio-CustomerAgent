import { useState, useEffect, useRef } from 'react';
import Form from 'react-bootstrap/Form';
import ListGroup from 'react-bootstrap/ListGroup';
import Spinner from 'react-bootstrap/Spinner';

interface Props {
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
}

export default function ProductNameCombobox({ value, onChange, required = false }: Props) {
  const [allNames, setAllNames] = useState<string[]>([]);
  const [filtered, setFiltered] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  /* Fetch product names once on mount (with 15s timeout) */
  useEffect(() => {
    let cancelled = false;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15_000);

    setLoading(true);
    fetch('/sr-api/v1/product-names', { signal: controller.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<{ names: string[]; count: number }>;
      })
      .then((data) => {
        if (!cancelled) {
          setAllNames(data.names);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.name === 'AbortError' ? 'Timed out loading products' : String(err));
        }
      })
      .finally(() => {
        clearTimeout(timer);
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; controller.abort(); };
  }, []);

  /* Filter on typing */
  useEffect(() => {
    if (!value.trim()) {
      setFiltered(allNames.slice(0, 50));
    } else {
      const lower = value.toLowerCase();
      setFiltered(allNames.filter((n) => n.toLowerCase().includes(lower)).slice(0, 50));
    }
  }, [value, allNames]);

  /* Close dropdown on outside click */
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSelect = (name: string) => {
    onChange(name);
    setOpen(false);
  };

  return (
    <div ref={wrapperRef} style={{ position: 'relative' }}>
      <Form.Label>
        Product Name {required && '*'}
        {loading && <Spinner animation="border" size="sm" className="ms-2" />}
      </Form.Label>
      <Form.Control
        value={value}
        onChange={(e) => { onChange(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder={loading ? 'Loading products…' : 'Type or select a product name'}
        required={required}
        autoComplete="off"
      />
      {error && <small className="text-warning d-block mt-1">Could not load product list — type a name manually.</small>}
      {open && filtered.length > 0 && (
        <ListGroup
          style={{
            position: 'absolute',
            zIndex: 1050,
            width: '100%',
            maxHeight: 250,
            overflowY: 'auto',
            boxShadow: '0 4px 12px rgba(0,0,0,.15)',
          }}
        >
          {filtered.map((name) => (
            <ListGroup.Item
              key={name}
              action
              active={name === value}
              onClick={() => handleSelect(name)}
              style={{ fontSize: '0.9rem', padding: '6px 12px' }}
            >
              {name}
            </ListGroup.Item>
          ))}
          {value.trim() && !allNames.includes(value) && (
            <ListGroup.Item disabled className="text-muted fst-italic" style={{ fontSize: '0.85rem' }}>
              Press Enter to use "{value}" as custom value
            </ListGroup.Item>
          )}
        </ListGroup>
      )}
    </div>
  );
}

import { FormEvent, useEffect, useState } from 'react';
import { AppConfig, putJson } from '../api';
import { isLanguage, Language, languages, translate } from '../i18n';

const privateIpv4 =
  /^(10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})$/;

function validIpv4(value: string): boolean {
  if (!privateIpv4.test(value)) {
    return false;
  }
  return value.split('.').every((part) => Number(part) >= 0 && Number(part) <= 255);
}

export function ConfigDialog({
  config,
  onClose,
  onSaved,
  language,
}: {
  config: AppConfig;
  onClose: () => void;
  onSaved: (config: AppConfig) => void;
  language: Language;
}) {
  const [form, setForm] = useState(config);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const t = (key: string) => translate(language, key);

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', onKeyDown);
    };
  }, [onClose]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!validIpv4(form.easynet_ip)) {
      setError(t('invalidPrivateIp'));
      return;
    }
    setSaving(true);
    setError('');
    try {
      const saved = await putJson<AppConfig>('/api/config', form);
      onSaved(saved);
      onClose();
    } catch {
      setError(t('configError'));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="config-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="config-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="dialog-header">
          <h2 id="config-title">{t('config')}</h2>
          <button className="dialog-close" type="button" aria-label={t('close')} onClick={onClose}>
            <span aria-hidden="true">×</span>
          </button>
        </div>
        <form onSubmit={submit}>
          <label>
            {t('language')}
            <select
              value={form.language}
              onChange={(event) => {
                if (isLanguage(event.target.value)) {
                  setForm({ ...form, language: event.target.value });
                }
              }}
            >
              {languages.map((item) => (
                <option value={item.value} key={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t('temperature')}
            <select
              value={form.temperature_unit}
              onChange={(event) =>
                setForm({ ...form, temperature_unit: event.target.value as 'c' | 'f' })
              }
            >
              <option value="c">°C</option>
              <option value="f">°F</option>
            </select>
          </label>
          <label>
            {t('easynetIp')}
            <input
              type="text"
              inputMode="decimal"
              value={form.easynet_ip}
              pattern="(?:[0-9]{1,3}[.]){3}[0-9]{1,3}"
              onChange={(event) => setForm({ ...form, easynet_ip: event.target.value })}
              required
            />
          </label>
          {error && <p className="form-error">{error}</p>}
          <div className="dialog-actions">
            <button type="button" className="secondary" onClick={onClose}>
              {t('cancel')}
            </button>
            <button type="submit" disabled={saving}>
              {saving ? t('saving') : t('save')}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}


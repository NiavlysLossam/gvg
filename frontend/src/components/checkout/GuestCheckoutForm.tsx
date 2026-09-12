import React, { useState } from 'react';
import {
  User,
  Mail,
  Phone,
  MapPin,
  ShieldCheck,
  AlertCircle,
  Lock,
  ArrowRight,
  Loader2,
} from 'lucide-react';
import { GuestOrderCreate, OrderOut } from '../../types/order';
import { createGuestOrder } from '../../lib/api';

interface GuestCheckoutFormProps {
  slug: string;
  sessionToken: string;
  totalPriceCents: number;
  totalLinearMeters: number;
  totalCount: number;
  disabled?: boolean;
  onSubmitOrder: (order: OrderOut) => void;
  onExpired?: () => void;
}

export const GuestCheckoutForm: React.FC<GuestCheckoutFormProps> = ({
  slug,
  sessionToken,
  totalPriceCents,
  totalLinearMeters,
  totalCount,
  disabled = false,
  onSubmitOrder,
  onExpired,
}) => {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [streetAddress, setStreetAddress] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [city, setCity] = useState('');
  const [honorAccepted, setHonorAccepted] = useState(false);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const validate = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!firstName.trim()) {
      newErrors.firstName = 'Le prénom est obligatoire.';
    }
    if (!lastName.trim()) {
      newErrors.lastName = 'Le nom de famille est obligatoire.';
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email.trim()) {
      newErrors.email = "L'adresse email est obligatoire.";
    } else if (!emailRegex.test(email.trim())) {
      newErrors.email = "L'adresse email saisie est invalide.";
    }

    const digitsOnly = phone.replace(/\D/g, '');
    if (!phone.trim()) {
      newErrors.phone = 'Le numéro de téléphone portable est obligatoire.';
    } else if (digitsOnly.length < 8 || digitsOnly.length > 15) {
      newErrors.phone = 'Le numéro de téléphone doit comporter entre 8 et 15 chiffres.';
    }

    if (!streetAddress.trim()) {
      newErrors.streetAddress = "L'adresse postale est obligatoire.";
    }

    if (!postalCode.trim()) {
      newErrors.postalCode = 'Le code postal est obligatoire.';
    } else if (!/^[0-9A-Za-z\s-]{2,10}$/.test(postalCode.trim())) {
      newErrors.postalCode = 'Le code postal est invalide.';
    }

    if (!city.trim()) {
      newErrors.city = 'La ville est obligatoire.';
    }

    if (!honorAccepted) {
      newErrors.honor =
        "L'attestation sur l'honneur est obligatoire pour participer au vide-grenier.";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitError(null);

    if (!validate()) {
      return;
    }

    setSubmitting(true);
    try {
      const payload: GuestOrderCreate = {
        session_token: sessionToken,
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: email.trim().toLowerCase(),
        phone: phone.trim(),
        street_address: streetAddress.trim(),
        postal_code: postalCode.trim(),
        city: city.trim(),
        honor_declaration_accepted: honorAccepted,
      };

      const createdOrder = await createGuestOrder(slug, payload);
      onSubmitOrder(createdOrder);
    } catch (err: any) {
      const detail = err?.detail || err?.message;
      let detailMsg = 'Erreur lors de la validation de la réservation';
      if (typeof detail === 'string') {
        detailMsg = detail;
      } else if (Array.isArray(detail) && detail.length > 0) {
        detailMsg = detail[0]?.msg || JSON.stringify(detail[0]);
      }
      detailMsg = detailMsg.replace(/^Value error,\s*/i, '');

      if (err?.status === 409 || detailMsg.includes('expiré')) {
        setSubmitError('Votre réservation temporaire a expiré, veuillez resélectionner vos stands.');
        onExpired?.();
      } else {
        setSubmitError(detailMsg);
      }
    } finally {
      setSubmitting(false);
    }
  };

  const formattedPrice = (totalPriceCents / 100).toLocaleString('fr-FR', {
    style: 'currency',
    currency: 'EUR',
  });

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-6 bg-white rounded-2xl p-6 sm:p-8 shadow-sm border border-gray-200"
      noValidate
    >
      {/* Header Reassurance Banner */}
      <div className="flex items-center gap-3 p-3.5 bg-emerald-50/70 border border-emerald-200/80 rounded-xl text-emerald-900 text-xs sm:text-sm">
        <Lock className="w-4 h-4 text-emerald-700 flex-shrink-0" />
        <span>
          <strong>Réservation sans mot de passe :</strong> Remplissez simplement vos coordonnées
          ci-dessous pour réserver vos {totalCount} emplacement{totalCount > 1 ? 's' : ''} ({totalLinearMeters} m).
        </span>
      </div>

      {submitError && (
        <div
          className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3 text-red-800 text-sm animate-fade-in"
          role="alert"
        >
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold">Impossible de valider votre réservation</p>
            <p className="mt-0.5 text-red-700">{submitError}</p>
          </div>
        </div>
      )}

      {/* Identité (Prénom & Nom) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label
            htmlFor="first_name"
            className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-1.5"
          >
            Prénom <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
              <User className="w-4 h-4" />
            </div>
            <input
              id="first_name"
              type="text"
              required
              autoComplete="given-name"
              disabled={disabled || submitting}
              value={firstName}
              onChange={(e) => {
                setFirstName(e.target.value);
                if (errors.firstName) setErrors((prev) => ({ ...prev, firstName: '' }));
              }}
              placeholder="Ex : Monique"
              className={`w-full pl-10 pr-3.5 py-2.5 rounded-xl border text-sm text-gray-900 placeholder-gray-400 transition outline-none focus:ring-2 focus:ring-emerald-600 ${
                errors.firstName
                  ? 'border-red-300 bg-red-50/30 focus:border-red-500'
                  : 'border-gray-300 bg-white hover:border-gray-400 focus:border-emerald-600'
              }`}
              aria-invalid={!!errors.firstName}
              aria-describedby={errors.firstName ? 'first_name-error' : undefined}
            />
          </div>
          {errors.firstName && (
            <p id="first_name-error" className="text-xs text-red-600 mt-1 font-medium">
              {errors.firstName}
            </p>
          )}
        </div>

        <div>
          <label
            htmlFor="last_name"
            className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-1.5"
          >
            Nom <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
              <User className="w-4 h-4" />
            </div>
            <input
              id="last_name"
              type="text"
              required
              autoComplete="family-name"
              disabled={disabled || submitting}
              value={lastName}
              onChange={(e) => {
                setLastName(e.target.value);
                if (errors.lastName) setErrors((prev) => ({ ...prev, lastName: '' }));
              }}
              placeholder="Ex : Durand"
              className={`w-full pl-10 pr-3.5 py-2.5 rounded-xl border text-sm text-gray-900 placeholder-gray-400 transition outline-none focus:ring-2 focus:ring-emerald-600 ${
                errors.lastName
                  ? 'border-red-300 bg-red-50/30 focus:border-red-500'
                  : 'border-gray-300 bg-white hover:border-gray-400 focus:border-emerald-600'
              }`}
              aria-invalid={!!errors.lastName}
              aria-describedby={errors.lastName ? 'last_name-error' : undefined}
            />
          </div>
          {errors.lastName && (
            <p id="last_name-error" className="text-xs text-red-600 mt-1 font-medium">
              {errors.lastName}
            </p>
          )}
        </div>
      </div>

      {/* Contact (Email & Téléphone) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label
            htmlFor="email"
            className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-1.5"
          >
            Adresse email <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
              <Mail className="w-4 h-4" />
            </div>
            <input
              id="email"
              type="email"
              required
              autoComplete="email"
              inputMode="email"
              disabled={disabled || submitting}
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (errors.email) setErrors((prev) => ({ ...prev, email: '' }));
              }}
              placeholder="monique.durand@exemple.fr"
              className={`w-full pl-10 pr-3.5 py-2.5 rounded-xl border text-sm text-gray-900 placeholder-gray-400 transition outline-none focus:ring-2 focus:ring-emerald-600 ${
                errors.email
                  ? 'border-red-300 bg-red-50/30 focus:border-red-500'
                  : 'border-gray-300 bg-white hover:border-gray-400 focus:border-emerald-600'
              }`}
              aria-invalid={!!errors.email}
              aria-describedby={errors.email ? 'email-error' : undefined}
            />
          </div>
          {errors.email ? (
            <p id="email-error" className="text-xs text-red-600 mt-1 font-medium">
              {errors.email}
            </p>
          ) : (
            <p className="text-[11px] text-gray-500 mt-1">
              Pour recevoir votre confirmation et attestation PDF.
            </p>
          )}
        </div>

        <div>
          <label
            htmlFor="phone"
            className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-1.5"
          >
            Téléphone portable <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
              <Phone className="w-4 h-4" />
            </div>
            <input
              id="phone"
              type="tel"
              required
              autoComplete="tel"
              inputMode="tel"
              disabled={disabled || submitting}
              value={phone}
              onChange={(e) => {
                setPhone(e.target.value);
                if (errors.phone) setErrors((prev) => ({ ...prev, phone: '' }));
              }}
              placeholder="06 12 34 56 78"
              className={`w-full pl-10 pr-3.5 py-2.5 rounded-xl border text-sm text-gray-900 placeholder-gray-400 transition outline-none focus:ring-2 focus:ring-emerald-600 ${
                errors.phone
                  ? 'border-red-300 bg-red-50/30 focus:border-red-500'
                  : 'border-gray-300 bg-white hover:border-gray-400 focus:border-emerald-600'
              }`}
              aria-invalid={!!errors.phone}
              aria-describedby={errors.phone ? 'phone-error' : undefined}
            />
          </div>
          {errors.phone ? (
            <p id="phone-error" className="text-xs text-red-600 mt-1 font-medium">
              {errors.phone}
            </p>
          ) : (
            <p className="text-[11px] text-gray-500 mt-1">
              Joignable le matin de la manifestation en cas d'imprévu.
            </p>
          )}
        </div>
      </div>

      {/* Adresse postale */}
      <div>
        <label
          htmlFor="street_address"
          className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-1.5"
        >
          Adresse postale (Rue, Numéro, Lieu-dit) <span className="text-red-500">*</span>
        </label>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-gray-400">
            <MapPin className="w-4 h-4" />
          </div>
          <input
            id="street_address"
            type="text"
            required
            autoComplete="street-address"
            disabled={disabled || submitting}
            value={streetAddress}
            onChange={(e) => {
              setStreetAddress(e.target.value);
              if (errors.streetAddress) setErrors((prev) => ({ ...prev, streetAddress: '' }));
            }}
            placeholder="Ex : 12 rue des Lilas"
            className={`w-full pl-10 pr-3.5 py-2.5 rounded-xl border text-sm text-gray-900 placeholder-gray-400 transition outline-none focus:ring-2 focus:ring-emerald-600 ${
              errors.streetAddress
                ? 'border-red-300 bg-red-50/30 focus:border-red-500'
                : 'border-gray-300 bg-white hover:border-gray-400 focus:border-emerald-600'
            }`}
            aria-invalid={!!errors.streetAddress}
            aria-describedby={errors.streetAddress ? 'street_address-error' : undefined}
          />
        </div>
        {errors.streetAddress && (
          <p id="street_address-error" className="text-xs text-red-600 mt-1 font-medium">
            {errors.streetAddress}
          </p>
        )}
      </div>

      {/* Code postal & Ville */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label
            htmlFor="postal_code"
            className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-1.5"
          >
            Code postal <span className="text-red-500">*</span>
          </label>
          <input
            id="postal_code"
            type="text"
            required
            autoComplete="postal-code"
            inputMode="numeric"
            disabled={disabled || submitting}
            value={postalCode}
            onChange={(e) => {
              setPostalCode(e.target.value);
              if (errors.postalCode) setErrors((prev) => ({ ...prev, postalCode: '' }));
            }}
            placeholder="35000"
            className={`w-full px-3.5 py-2.5 rounded-xl border text-sm text-gray-900 placeholder-gray-400 transition outline-none focus:ring-2 focus:ring-emerald-600 ${
              errors.postalCode
                ? 'border-red-300 bg-red-50/30 focus:border-red-500'
                : 'border-gray-300 bg-white hover:border-gray-400 focus:border-emerald-600'
            }`}
            aria-invalid={!!errors.postalCode}
            aria-describedby={errors.postalCode ? 'postal_code-error' : undefined}
          />
          {errors.postalCode && (
            <p id="postal_code-error" className="text-xs text-red-600 mt-1 font-medium">
              {errors.postalCode}
            </p>
          )}
        </div>

        <div className="sm:col-span-2">
          <label
            htmlFor="city"
            className="block text-xs font-bold uppercase tracking-wider text-gray-700 mb-1.5"
          >
            Ville <span className="text-red-500">*</span>
          </label>
          <input
            id="city"
            type="text"
            required
            autoComplete="address-level2"
            disabled={disabled || submitting}
            value={city}
            onChange={(e) => {
              setCity(e.target.value);
              if (errors.city) setErrors((prev) => ({ ...prev, city: '' }));
            }}
            placeholder="Rennes"
            className={`w-full px-3.5 py-2.5 rounded-xl border text-sm text-gray-900 placeholder-gray-400 transition outline-none focus:ring-2 focus:ring-emerald-600 ${
              errors.city
                ? 'border-red-300 bg-red-50/30 focus:border-red-500'
                : 'border-gray-300 bg-white hover:border-gray-400 focus:border-emerald-600'
            }`}
            aria-invalid={!!errors.city}
            aria-describedby={errors.city ? 'city-error' : undefined}
          />
          {errors.city && (
            <p id="city-error" className="text-xs text-red-600 mt-1 font-medium">
              {errors.city}
            </p>
          )}
        </div>
      </div>

      {/* Attestation sur l'honneur obligatoire (art. L310-2 du Code de commerce) */}
      <div
        className={`p-4 rounded-xl border transition ${
          errors.honor
            ? 'bg-red-50/50 border-red-300 ring-2 ring-red-200'
            : honorAccepted
            ? 'bg-emerald-50/50 border-emerald-300'
            : 'bg-amber-50/40 border-amber-200'
        }`}
      >
        <div className="flex items-start gap-3">
          <div className="flex items-center h-5 mt-0.5">
            <input
              id="honor_declaration"
              name="honor_declaration"
              type="checkbox"
              required
              disabled={disabled || submitting}
              checked={honorAccepted}
              onChange={(e) => {
                setHonorAccepted(e.target.checked);
                if (errors.honor) setErrors((prev) => ({ ...prev, honor: '' }));
              }}
              className="w-5 h-5 text-emerald-700 border-gray-300 rounded-md focus:ring-emerald-600 cursor-pointer"
              aria-invalid={!!errors.honor}
              aria-describedby="honor_declaration-text"
            />
          </div>
          <div className="flex-1 text-xs sm:text-sm">
            <label
              htmlFor="honor_declaration"
              id="honor_declaration-text"
              className="font-medium text-gray-900 cursor-pointer leading-relaxed block"
            >
              Je certifie sur l'honneur être un particulier et ne pas participer à plus de 2 ventes au
              déballage dans l'année (art. L310-2 du Code de commerce).
            </label>
            <p className="text-[11px] text-gray-500 mt-1 flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-600 flex-shrink-0" />
              <span>
                Obligation légale française simplifiée : aucune pièce d'identité n'est à téléverser en
                ligne.
              </span>
            </p>
          </div>
        </div>
        {errors.honor && (
          <p className="text-xs text-red-700 mt-2 font-semibold flex items-center gap-1.5">
            <AlertCircle className="w-4 h-4 flex-shrink-0 text-red-600" />
            <span>{errors.honor}</span>
          </p>
        )}
      </div>

      {/* Submit Button */}
      <div className="pt-2">
        <button
          type="submit"
          disabled={disabled || submitting}
          className={`w-full py-3.5 px-6 rounded-xl font-bold text-white shadow-sm flex items-center justify-center gap-2.5 transition active:scale-[0.99] ${
            disabled || submitting
              ? 'bg-gray-400 cursor-not-allowed opacity-80'
              : 'bg-emerald-700 hover:bg-emerald-800'
          }`}
        >
          {submitting ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Validation de votre réservation...</span>
            </>
          ) : (
            <>
              <span>Continuer vers le paiement ({formattedPrice})</span>
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </button>
        <p className="text-center text-[11px] text-gray-400 mt-2">
          Paiement bancaire 100% sécurisé via Stripe à l'étape suivante.
        </p>
      </div>
    </form>
  );
};

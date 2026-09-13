import React, { useState, useEffect } from 'react';
import { loadStripe, Stripe } from '@stripe/stripe-js';
import {
  Elements,
  PaymentElement,
  useStripe,
  useElements,
} from '@stripe/react-stripe-js';
import { ShieldCheck, Lock, AlertCircle, Loader2, CreditCard } from 'lucide-react';
import { OrderOut, PaymentIntentResponse } from '../../types/order';
import { createPaymentIntent, ApiError } from '../../lib/api';

interface StripePaymentFormProps {
  slug: string;
  order: OrderOut;
  onSuccess: (orderId: string) => void;
  onExpired?: () => void;
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
  }).format(price);
}

// Inner form component mounted inside Stripe Elements context
const CheckoutFormInner: React.FC<{
  slug: string;
  order: OrderOut;
  onSuccess: (orderId: string) => void;
}> = ({ slug, order, onSuccess }) => {
  const stripe = useStripe();
  const elements = useElements();
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!stripe || !elements) {
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);

    try {
      const returnUrl = `${window.location.origin}/e/${encodeURIComponent(slug)}/confirmation/${encodeURIComponent(order.id)}?token=${encodeURIComponent(order.access_token)}`;

      const result = await stripe.confirmPayment({
        elements,
        confirmParams: {
          return_url: returnUrl,
          payment_method_data: {
            billing_details: {
              name: `${order.first_name} ${order.last_name}`.trim(),
              email: order.email,
              phone: order.phone,
              address: {
                line1: order.street_address,
                postal_code: order.postal_code,
                city: order.city,
                country: 'FR',
              },
            },
          },
        },
        redirect: 'if_required',
      });

      if (result.error) {
        // Localized French friendly fallback if error message is technical
        let msg = result.error.message || 'Une erreur est survenue lors du paiement.';
        if (result.error.type === 'card_error') {
          if (result.error.code === 'card_declined') {
            msg = 'Votre carte a été refusée. Veuillez vérifier vos fonds ou utiliser une autre carte.';
          } else if (result.error.code === 'expired_card') {
            msg = 'Votre carte a expiré. Veuillez utiliser une autre carte bancaire.';
          } else if (result.error.code === 'incorrect_cvc') {
            msg = 'Le code de sécurité (CVC) est incorrect.';
          } else if (result.error.code === 'insufficient_funds') {
            msg = 'Fonds insuffisants sur votre compte. Veuillez utiliser un autre moyen de paiement.';
          }
        }
        setErrorMessage(msg);
        setSubmitting(false);
      } else if (
        result.paymentIntent &&
        (result.paymentIntent.status === 'succeeded' ||
          result.paymentIntent.status === 'processing' ||
          result.paymentIntent.status === 'requires_capture')
      ) {
        // Immediate in-app transition when redirect is not required (e.g. nominal card or manual capture)
        onSuccess(order.id);
      } else {
        // Handled/dismissed 3DS modal or unhandled status: reset submitting state
        setSubmitting(false);
      }
    } catch (err: any) {
      setErrorMessage(err?.message || 'Erreur imprévue lors de la validation du paiement.');
      setSubmitting(false);
    }
  };


  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {errorMessage && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-800 text-sm flex items-start gap-3 animate-fade-in">
          <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-bold">Le paiement n'a pas pu aboutir</p>
            <p className="text-xs leading-relaxed text-red-700">{errorMessage}</p>
          </div>
        </div>
      )}

      <div className="bg-white rounded-2xl p-5 border border-gray-200 shadow-sm space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-gray-100">
          <span className="text-sm font-bold text-gray-900 flex items-center gap-2">
            <CreditCard className="w-4 h-4 text-emerald-700" />
            <span>Coordonnées bancaires</span>
          </span>
          <span className="text-xs text-gray-500 font-medium flex items-center gap-1">
            <Lock className="w-3 h-3 text-emerald-600" />
            <span>Paiement sécurisé</span>
          </span>
        </div>

        {/* Stripe Elements Component */}
        <PaymentElement
          id="payment-element"
          options={{
            layout: 'tabs',
          }}
        />
      </div>

      {/* Submit Button with Smooth Loading State */}
      <button
        type="submit"
        disabled={!stripe || !elements || submitting}
        className="w-full flex items-center justify-center gap-2 py-4 px-6 rounded-xl bg-emerald-700 hover:bg-emerald-800 disabled:bg-emerald-400 text-white font-bold text-base shadow-sm transition active:scale-[0.99] cursor-pointer disabled:cursor-not-allowed"
      >
        {submitting ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            <span>Validation sécurisée en cours...</span>
          </>
        ) : (
          <>
            <Lock className="w-4 h-4" />
            <span>Régler ma commande ({formatPrice(order.total_price)})</span>
          </>
        )}
      </button>

      {/* Security Reassurance Footnote */}
      <div className="pt-2 flex flex-col items-center justify-center text-center text-xs text-gray-500 space-y-1.5">
        <p className="flex items-center gap-1.5 text-gray-600 font-medium">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          <span>Paiement 100% sécurisé crypté de bout en bout via Stripe</span>
        </p>
        <p className="text-[11px] text-gray-400">
          Vos coordonnées bancaires ne transitent jamais par nos serveurs.
        </p>
      </div>
    </form>
  );
};

export const StripePaymentForm: React.FC<StripePaymentFormProps> = ({
  slug,
  order,
  onSuccess,
  onExpired,
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [paymentIntentData, setPaymentIntentData] = useState<PaymentIntentResponse | null>(null);
  const [stripePromise, setStripePromise] = useState<Promise<Stripe | null> | null>(null);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);
    setError(null);

    createPaymentIntent(slug, order.id, order.access_token)
      .then((data) => {
        if (!isMounted) return;
        setPaymentIntentData(data);
        if (data.publishable_key) {
          setStripePromise(loadStripe(data.publishable_key));
        } else {
          setError('Clé publique Stripe manquante sur le serveur.');
        }
        setLoading(false);
      })
      .catch((err: any) => {
        if (!isMounted) return;
        if (err instanceof ApiError && err.status === 409) {
          const detailStr = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
          const lowerDetail = detailStr.toLowerCase();
          if (
            lowerDetail.includes('confirmée') ||
            lowerDetail.includes('confirmee') ||
            lowerDetail.includes('validation') ||
            lowerDetail.includes('approbation') ||
            lowerDetail.includes('pending_approval') ||
            lowerDetail.includes('approval')
          ) {
            onSuccess(order.id);
            return;
          }
          if (detailStr.includes('expiré')) {
            if (onExpired) {
              onExpired();
              return;
            }
          }
        }
        const errorMsg = typeof err?.detail === 'string' ? err.detail : err?.message || 'Impossible d’initialiser le paiement sécurisé.';
        setError(errorMsg);
        setLoading(false);
      });


    return () => {
      isMounted = false;
    };
  }, [slug, order.id, order.access_token, onExpired, onSuccess]);

  if (loading) {
    return (
      <div className="bg-white rounded-3xl p-8 border border-gray-200 shadow-sm text-center space-y-4">
        <div className="w-14 h-14 bg-emerald-50 text-emerald-700 rounded-2xl flex items-center justify-center mx-auto">
          <Loader2 className="w-7 h-7 animate-spin" />
        </div>
        <h3 className="text-lg font-bold text-gray-900">Préparation du paiement sécurisé...</h3>
        <p className="text-xs text-gray-500 max-w-sm mx-auto">
          Connexion au serveur bancaire sécurisé Stripe en cours...
        </p>
      </div>
    );
  }

  if (error || !paymentIntentData || !stripePromise) {
    return (
      <div className="bg-white rounded-3xl p-8 border border-gray-200 shadow-sm text-center space-y-4">
        <div className="w-14 h-14 bg-red-50 text-red-600 rounded-2xl flex items-center justify-center mx-auto">
          <AlertCircle className="w-7 h-7" />
        </div>
        <h3 className="text-lg font-bold text-gray-900">Échec d'initialisation</h3>
        <p className="text-xs text-gray-600 max-w-sm mx-auto leading-relaxed">{error}</p>
        {onExpired && (
          <button
            onClick={onExpired}
            className="mt-4 px-5 py-2.5 rounded-xl bg-emerald-700 hover:bg-emerald-800 text-white text-xs font-bold transition"
          >
            Retourner au plan
          </button>
        )}
      </div>
    );
  }

  return (
    <Elements
      stripe={stripePromise}
      options={{
        clientSecret: paymentIntentData.client_secret,
        locale: 'fr',
        appearance: {
          theme: 'stripe',
          variables: {
            colorPrimary: '#166534',
            colorBackground: '#ffffff',
            colorText: '#1f2937',
            colorDanger: '#dc2626',
            borderRadius: '12px',
          },
        },
      }}
    >
      <CheckoutFormInner slug={slug} order={order} onSuccess={onSuccess} />
    </Elements>
  );
};

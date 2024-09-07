from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Rating, SpecificRating, Tutor
from .serializers import RatingSerializer

@api_view(['POST'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def rate_tutor(request):
    try:
        tutor_id = request.data['tutor_id']
        submitted_rating = request.data['rating']

        if submitted_rating < 1 or submitted_rating > 5:
            return Response({"error": "Rating must be between 1 and 5."}, status=status.HTTP_400_BAD_REQUEST)

        tutor = get_object_or_404(Tutor, pk=tutor_id)
        rating_model, created = Rating.objects.get_or_create(tutor=tutor)

        user = request.user
        if tutor.user == user:
            return Response({"error": "You cannot rate yourself."}, status=status.HTTP_400_BAD_REQUEST)

        specific_rating, created = SpecificRating.objects.get_or_create(
            user=user, 
            related_rating=rating_model,
            defaults={'rating': submitted_rating}
        )
        
        if not created:
            old_rating = specific_rating.rating
            specific_rating.rating = submitted_rating
            specific_rating.save()
            rating_model.rating = (
                rating_model.rating * rating_model.num_of_ratings - old_rating + submitted_rating
            ) / rating_model.num_of_ratings
        else:
            rating_model.num_of_ratings += 1
            rating_model.rating = (
                rating_model.rating * (rating_model.num_of_ratings - 1) + submitted_rating
            ) / rating_model.num_of_ratings
            specific_rating.save()
        
        rating_model.save()
        serializer = RatingSerializer(rating_model)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Tutor.DoesNotExist:
        return Response({"error": "Tutor not found."}, status=status.HTTP_404_NOT_FOUND)
    except KeyError:
        return Response({"error": "tutor_id and rating are required."}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def delete_rating(request):
    try:
        tutor_id = request.data['tutor_id']
        tutor = get_object_or_404(Tutor, pk=tutor_id)
        user = request.user

        specific_rating = get_object_or_404(SpecificRating, user=user, related_rating__tutor=tutor)

        rating_model = specific_rating.related_rating
        if rating_model.num_of_ratings > 1:
            rating_model.rating = (rating_model.rating * rating_model.num_of_ratings - specific_rating.rating) / (rating_model.num_of_ratings - 1)
        else:
            rating_model.rating = 0
        rating_model.num_of_ratings -= 1
        rating_model.save()

        specific_rating.delete()

        return Response({"message": "Rating deleted successfully."}, status=status.HTTP_200_OK)
    except SpecificRating.DoesNotExist:
        return Response({"error": "Rating not found."}, status=status.HTTP_404_NOT_FOUND)
    except Tutor.DoesNotExist:
        return Response({"error": "Tutor not found."}, status=status.HTTP_404_NOT_FOUND)
    except KeyError:
        return Response({"error": "tutor_id is required."}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_tutor_rating(request):
    tutor_id = request.query_params.get('tutor_id')
    tutor = get_object_or_404(Tutor, pk=tutor_id)
    rating = get_object_or_404(Rating, tutor=tutor)
    serializer = RatingSerializer(rating)
    return Response(serializer.data)

@api_view(['GET'])
@authentication_classes([SessionAuthentication, TokenAuthentication])
@permission_classes([IsAuthenticated])
def get_user_rating(request):
    tutor_id = request.query_params.get('tutor_id')
    tutor = get_object_or_404(Tutor, pk=tutor_id)
    rating = get_object_or_404(Rating, tutor=tutor)
    user = request.user

    try:
        specific_rating = SpecificRating.objects.get(related_rating=rating, user=user)
        user_rating = specific_rating.rating
        rated = True
    except SpecificRating.DoesNotExist:
        user_rating = None
        rated = False

    return Response({"is_rated": rated, "rating": user_rating})